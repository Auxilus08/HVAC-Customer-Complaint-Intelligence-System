"""Celery task — VADER sentiment scoring via hvac-ml SentimentAnalyzer.

This worker NEVER instantiates VADER directly. Thresholds and labels are owned
by ``pipeline.sentiment.SentimentAnalyzer`` — change them there, not here.
"""

from __future__ import annotations

from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.config import get_settings
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)
settings = get_settings()


class SentimentTask(Task):
    abstract = True
    _analyzer = None
    _session_factory = None

    @property
    def analyzer(self):  # type: ignore[override]
        if self._analyzer is None:
            from pipeline.sentiment import SentimentAnalyzer

            self._analyzer = SentimentAnalyzer()
            logger.info("sentiment_analyzer_loaded")
        return self._analyzer

    @property
    def session_factory(self):
        if self._session_factory is None:
            from app.db.session import get_session_factory

            self._session_factory = get_session_factory()
        return self._session_factory


@celery_app.task(
    bind=True,
    base=SentimentTask,
    name="app.workers.sentiment_worker.score_sentiment",
    max_retries=3,
    default_retry_delay=15,
    queue="sentiment",
)
def score_sentiment(self: SentimentTask, complaint_id: int) -> dict:  # type: ignore[misc]
    """Compute VADER sentiment via hvac-ml and persist score + label."""
    import asyncio

    logger.info("sentiment_task_started", complaint_id=complaint_id)

    async def _run() -> dict:
        from app.models.complaint import Complaint

        async with self.session_factory() as session:
            result = await session.execute(
                select(Complaint).where(Complaint.id == complaint_id)
            )
            complaint = result.scalar_one_or_none()
            if complaint is None:
                return {"status": "skipped", "reason": "not_found"}

            sentiment = self.analyzer.score(complaint.clean_text)

            complaint.sentiment_score = sentiment.compound
            complaint.sentiment_label = sentiment.label
            await session.commit()

        logger.debug(
            "sentiment_scored",
            complaint_id=complaint_id,
            compound=sentiment.compound,
            label=sentiment.label,
        )
        return {
            "status": "ok",
            "complaint_id": complaint_id,
            "label": sentiment.label,
        }

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run())
        loop.close()
        logger.info("sentiment_task_completed", complaint_id=complaint_id)
        return result
    except Exception as exc:
        logger.error(
            "sentiment_task_failed",
            complaint_id=complaint_id,
            error=str(exc),
            retry_count=self.request.retries,
        )
        raise self.retry(exc=exc, countdown=15 * (2**self.request.retries)) from exc
