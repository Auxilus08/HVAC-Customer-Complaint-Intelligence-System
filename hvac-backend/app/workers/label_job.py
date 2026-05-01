"""Celery task — auto-label clusters via hvac-ml ClusterLabeler.

Delegates ALL labeling logic (Jaccard gate, PII strip, Gemini API call) to
``pipeline.labeler.ClusterLabeler``. This worker NEVER calls Gemini directly
and NEVER computes Jaccard distance locally.
"""

from __future__ import annotations

from datetime import UTC, datetime

from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.config import get_settings
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)
settings = get_settings()


class LabelTask(Task):
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
    base=LabelTask,
    name="app.workers.label_job.label_clusters",
    max_retries=2,
    default_retry_delay=60,
    queue="batch",
)
def label_clusters(self: LabelTask, run_id: str) -> dict:  # type: ignore[misc]
    """Label changed clusters using ClusterLabeler — Jaccard-gated."""
    import asyncio

    from pipeline.labeler import ClusterLabeler

    logger.info("label_job_started", run_id=run_id)

    async def _run() -> dict:
        from app.models.cluster import Cluster
        from app.models.complaint import Complaint

        labeler = ClusterLabeler(
            model=settings.GEMINI_MODEL,
            api_key=settings.GOOGLE_API_KEY,
        )

        async with self.session_factory() as session:
            clusters_result = await session.execute(
                select(Cluster).where(Cluster.last_run_id == run_id)
            )
            clusters = clusters_result.scalars().all()

            cluster_complaints: dict[int, list[str]] = {}
            new_fingerprints: dict[int, set[int]] = {}
            old_fingerprints: dict[int, set[int]] = {}
            previous_labels: dict[int, str] = {}

            for cluster in clusters:
                members_result = await session.execute(
                    select(Complaint.id, Complaint.clean_text).where(
                        Complaint.cluster_id == cluster.id
                    )
                )
                rows = members_result.fetchall()
                if not rows:
                    continue
                member_ids = {int(r[0]) for r in rows}
                samples = [r[1] for r in rows[: labeler.sample_limit]]

                cluster_complaints[cluster.id] = samples
                new_fingerprints[cluster.id] = member_ids

                # We only have a fingerprint hash on the Cluster row, not the
                # raw set, so the gate compares hashes when available and
                # treats a hash mismatch as "always relabel".
                if cluster.previous_member_ids:
                    old_fingerprints[cluster.id] = set(cluster.previous_member_ids)
                if cluster.label:
                    previous_labels[cluster.id] = cluster.label

            labels = labeler.label_all_clusters(
                cluster_complaints=cluster_complaints,
                old_fingerprints=old_fingerprints,
                new_fingerprints=new_fingerprints,
                previous_labels=previous_labels,
            )

            llm_calls = sum(
                1
                for cid, label in labels.items()
                if previous_labels.get(cid) != label
            )

            now = datetime.now(tz=UTC)
            for cluster in clusters:
                if cluster.id not in labels:
                    continue
                cluster.label = labels[cluster.id]
                cluster.label_updated_at = now
                cluster.previous_member_ids = sorted(
                    new_fingerprints.get(cluster.id, set())
                )

            await session.commit()

        return {"run_id": run_id, "llm_calls_made": llm_calls}

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run())
        loop.close()
        logger.info("label_job_completed", run_id=run_id, **result)
        return result
    except Exception as exc:
        logger.error("label_job_failed", run_id=run_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries)) from exc
