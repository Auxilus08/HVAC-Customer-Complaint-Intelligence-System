"""Celery task — week-over-week growth + cost exposure via hvac-ml TrendDetector.

Delegates ALL trend math (growth %, emerging flag, cost exposure) to
``pipeline.trend_detector.TrendDetector``. This worker NEVER computes WoW
percentages or emerging flags locally.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.config import get_settings
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)
settings = get_settings()


class TrendTask(Task):
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
    base=TrendTask,
    name="app.workers.trend_job.compute_trends",
    max_retries=2,
    default_retry_delay=60,
    queue="batch",
)
def compute_trends(self: TrendTask, run_id: str) -> dict:  # type: ignore[misc]
    """Compute WoW growth, cost exposure, emerging flags via TrendDetector."""
    import asyncio

    from pipeline.trend_detector import TrendDetector

    logger.info("trend_job_started", run_id=run_id)

    async def _run() -> dict:
        from sqlalchemy.dialects.postgresql import insert

        from app.models.cluster import Cluster
        from app.models.complaint import Complaint
        from app.models.trend_snapshot import TrendSnapshot

        async with self.session_factory() as session:
            clusters_result = await session.execute(
                select(Cluster).where(Cluster.last_run_id == run_id)
            )
            clusters = clusters_result.scalars().all()

            cluster_ids = [c.id for c in clusters]
            if not cluster_ids:
                logger.warning("trend_job_no_clusters", run_id=run_id)
                return {"run_id": run_id, "emerging_clusters": 0}

            # Pull all in-window complaint rows once and feed to TrendDetector.
            complaints_result = await session.execute(
                select(
                    Complaint.cluster_id,
                    Complaint.created_at,
                    Complaint.sentiment_score,
                ).where(Complaint.cluster_id.in_(cluster_ids))
            )
            rows = complaints_result.fetchall()
            df = pd.DataFrame(
                rows, columns=["cluster_id", "created_at", "sentiment_score"]
            )

            detector = TrendDetector()
            trend_results = detector.compute_trends(
                df, lookback_days=30, as_of=datetime.now(UTC),
            )
            trends_by_id = {t.cluster_id: t for t in trend_results}

            # Per-cluster avg sentiment for the snapshot
            avg_sent = (
                df.groupby("cluster_id")["sentiment_score"]
                .mean()
                .to_dict()
            )

            today = date.today()
            emerging_count = 0

            for cluster in clusters:
                t = trends_by_id.get(cluster.id)
                if t is None:
                    continue

                # is_emerging requires our minimum-volume safety check too.
                is_emerging = (
                    t.is_emerging
                    and t.current_week_count >= settings.MIN_COMPLAINTS_FOR_ALERT
                )

                cluster.growth_pct_wow = t.growth_pct / 100.0
                cluster.is_emerging = is_emerging
                cluster.avg_sentiment = (
                    float(avg_sent.get(cluster.id))
                    if cluster.id in avg_sent and pd.notna(avg_sent[cluster.id])
                    else None
                )
                cluster.cost_exposure_estimate = Decimal(str(t.window_cost_exposure))

                if is_emerging:
                    emerging_count += 1

                stmt = insert(TrendSnapshot).values(
                    cluster_id=cluster.id,
                    snapshot_date=today,
                    complaint_count=cluster.member_count or 0,
                    avg_sentiment=cluster.avg_sentiment,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["cluster_id", "snapshot_date"],
                    set_={
                        "complaint_count": cluster.member_count or 0,
                        "avg_sentiment": cluster.avg_sentiment,
                    },
                )
                await session.execute(stmt)

            await session.commit()

        logger.info(
            "trend_job_completed",
            run_id=run_id,
            clusters_processed=len(clusters),
            emerging=emerging_count,
        )
        return {"run_id": run_id, "emerging_clusters": emerging_count}

    try:
        result = asyncio.run(_run())
        return result
    except Exception as exc:
        logger.error("trend_job_failed", run_id=run_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries)) from exc
