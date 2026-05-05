"""Celery batch task — UMAP + HDBSCAN clustering nightly job.

Delegates ALL clustering logic to ``pipeline.clusterer.Clusterer`` from
hvac-ml. This worker NEVER imports umap or hdbscan directly. The two-stage
UMAP (50D for clustering, 2D for visualisation) lives in Clusterer.fit().
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime

import numpy as np
from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy import select, update

from app.config import get_settings
from app.workers.celery_app import celery_app

_celery_logger = get_task_logger(__name__)


class _KwargAdapter:
    """Wrap stdlib celery logger so structlog-style ``key=value`` kwargs
    are formatted into the message instead of crashing logging.Logger._log."""

    def __init__(self, base):
        self._base = base

    def _fmt(self, msg, **kwargs):
        if not kwargs:
            return msg
        extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
        return f"{msg} {extras}"

    def info(self, msg, *args, **kwargs):
        self._base.info(self._fmt(msg, **kwargs), *args)

    def warning(self, msg, *args, **kwargs):
        self._base.warning(self._fmt(msg, **kwargs), *args)

    def error(self, msg, *args, **kwargs):
        self._base.error(self._fmt(msg, **kwargs), *args)

    def exception(self, msg, *args, **kwargs):
        self._base.exception(self._fmt(msg, **kwargs), *args)

    def debug(self, msg, *args, **kwargs):
        self._base.debug(self._fmt(msg, **kwargs), *args)


logger = _KwargAdapter(_celery_logger)
settings = get_settings()


class ClusterTask(Task):
    abstract = True
    _session_factory = None

    @property
    def session_factory(self):
        if self._session_factory is None:
            from app.db.session import get_session_factory

            self._session_factory = get_session_factory()
        return self._session_factory


@celery_app.task(
    bind=True,
    base=ClusterTask,
    name="app.workers.cluster_job.run_nightly_batch",
    max_retries=1,
    queue="batch",
    time_limit=3600,
)
def run_nightly_batch(self: ClusterTask) -> dict:  # type: ignore[misc]
    """Nightly pipeline: load embeddings → Clusterer.fit() → persist results."""
    import asyncio

    run_id = (
        f"run_{datetime.now(tz=UTC).replace(tzinfo=None).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )
    logger.info("nightly_batch_started", run_id=run_id)

    async def _run() -> dict:
        from pipeline.clusterer import Clusterer

        from app.models.batch_run_log import BatchRunLog
        from app.models.cluster import Cluster
        from app.models.complaint import Complaint
        from app.models.umap_coord import UmapCoord

        async with self.session_factory() as session:
            run_log = BatchRunLog(
                run_id=run_id,
                started_at=datetime.now(tz=UTC).replace(tzinfo=None),
                status="running",
            )
            session.add(run_log)
            await session.flush()

            result = await session.execute(
                select(Complaint.id, Complaint.embedding).where(
                    Complaint.embedding.is_not(None),
                    Complaint.status.in_(["embedded", "processed"]),
                )
            )
            rows = result.fetchall()

            if len(rows) < settings.HDBSCAN_MIN_CLUSTER_SIZE * 2:
                logger.warning("nightly_batch_insufficient_data", count=len(rows))
                run_log.status = "skipped"
                run_log.complaints_processed = len(rows)
                run_log.completed_at = datetime.now(tz=UTC).replace(tzinfo=None)
                await session.commit()
                return {"status": "skipped", "reason": "insufficient_data"}

            ids = [r[0] for r in rows]
            embeddings = np.array([r[1] for r in rows], dtype=np.float32)

            # ── Single source of truth: hvac-ml Clusterer ─────────────────
            clusterer = Clusterer(
                umap_n_components_cluster=settings.UMAP_N_COMPONENTS_CLUSTER,
                umap_n_components_viz=settings.UMAP_N_COMPONENTS_VIZ,
                hdbscan_min_cluster_size=settings.HDBSCAN_MIN_CLUSTER_SIZE,
                random_state=settings.UMAP_RANDOM_STATE,
            )
            cluster_result = clusterer.fit(embeddings, ids=ids)

            if (
                len(cluster_result.labels) != len(ids)
                or len(cluster_result.probabilities) != len(ids)
                or len(cluster_result.coords_2d) != len(ids)
            ):
                raise RuntimeError(
                    "clusterer returned arrays whose length does not match input ids"
                )

            # ── Upsert cluster rows (match by fingerprint to avoid unbounded growth)
            cluster_id_map: dict[int, int] = {}  # hdbscan_label -> DB id
            for hdb_label, size in cluster_result.cluster_sizes.items():
                mask = cluster_result.labels == hdb_label
                centroid = embeddings[mask].mean(axis=0).tolist()
                fp_hash = cluster_result.fingerprints[hdb_label]

                # Try to find an existing cluster with the same fingerprint.
                existing_result = await session.execute(
                    select(Cluster).where(
                        Cluster.fingerprint_hash == fp_hash
                    ).limit(1)
                )
                existing = existing_result.scalar_one_or_none()

                if existing is not None:
                    # Update existing cluster row in place.
                    existing.centroid = centroid
                    existing.member_count = int(size)
                    existing.last_run_id = run_id
                    existing.is_emerging = False
                    cluster_id_map[hdb_label] = existing.id
                else:
                    # Genuinely new cluster pattern — create a new row.
                    cluster_row = Cluster(
                        centroid=centroid,
                        member_count=int(size),
                        last_run_id=run_id,
                        is_emerging=False,
                        fingerprint_hash=fp_hash,
                    )
                    session.add(cluster_row)
                    await session.flush()
                    cluster_id_map[hdb_label] = cluster_row.id

            # ── Update complaints with cluster assignments ─────────────────
            for i, complaint_id in enumerate(ids):
                hdb_label = int(cluster_result.labels[i])
                db_cluster_id = cluster_id_map.get(hdb_label)  # None for noise
                await session.execute(
                    update(Complaint)
                    .where(Complaint.id == complaint_id)
                    .values(
                        cluster_id=db_cluster_id,
                        hdbscan_conf=float(cluster_result.probabilities[i]),
                        status="processed",
                        processed_at=datetime.now(tz=UTC).replace(tzinfo=None),
                    )
                )

            # ── Persist 2D viz coords ─────────────────────────────────────
            for i, complaint_id in enumerate(ids):
                coord = UmapCoord(
                    complaint_id=complaint_id,
                    run_id=run_id,
                    x=float(cluster_result.coords_2d[i, 0]),
                    y=float(cluster_result.coords_2d[i, 1]),
                )
                session.add(coord)

            run_log.status = "completed"
            run_log.completed_at = datetime.now(tz=UTC).replace(tzinfo=None)
            run_log.complaints_processed = len(ids)
            run_log.clusters_found = cluster_result.n_clusters
            sil = cluster_result.silhouette_score
            run_log.silhouette_score = None if math.isnan(sil) else sil
            run_log.noise_pct = cluster_result.noise_pct / 100.0
            await session.commit()

        # Trigger label + trend jobs after clustering completes
        celery_app.send_task(
            "app.workers.label_job.label_clusters",
            args=[run_id],
            queue="batch",
        )
        celery_app.send_task(
            "app.workers.trend_job.compute_trends",
            args=[run_id],
            queue="batch",
        )

        logger.info(
            "nightly_batch_completed",
            run_id=run_id,
            clusters=cluster_result.n_clusters,
            noise_pct=round(cluster_result.noise_pct, 2),
            silhouette=None if math.isnan(sil) else round(sil, 3),
        )
        return {
            "run_id": run_id,
            "clusters": cluster_result.n_clusters,
            "complaints_processed": len(ids),
            "noise_pct": cluster_result.noise_pct,
        }

    try:
        result = asyncio.run(_run())
        return result
    except Exception as exc:
        logger.exception("nightly_batch_failed", run_id=run_id, error=str(exc))
        raise self.retry(exc=exc) from exc
