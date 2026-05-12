"""Celery task — VADER sentiment scoring via hvac-ml SentimentAnalyzer.

This worker NEVER instantiates VADER directly. Thresholds and labels are owned
by ``pipeline.sentiment.SentimentAnalyzer`` — change them there, not here.
"""

from __future__ import annotations

from celery import Task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)
settings = get_settings()


class SentimentTask(Task):
    abstract = True
    _analyzer = None
    _session_factory: sessionmaker[Session] | None = None

    @property
    def analyzer(self):  # type: ignore[override]
        if self._analyzer is None:
            from pipeline.sentiment import SentimentAnalyzer

            self._analyzer = SentimentAnalyzer()
            logger.info("sentiment_analyzer_loaded")
        return self._analyzer

    @property
    def session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            engine = create_engine(
                settings.DATABASE_SYNC_URL,
                pool_size=2,
                max_overflow=1,
                pool_pre_ping=True,
                echo=False,
            )
            self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
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
    from app.models.complaint import Complaint

    try:
        with self.session_factory() as session:
            complaint = session.execute(
                select(Complaint).where(Complaint.id == complaint_id)
            ).scalar_one_or_none()
            if complaint is None:
                return {"status": "skipped", "reason": "not_found"}

            sentiment = self.analyzer.score(complaint.clean_text)
            complaint.sentiment_score = sentiment.compound
            complaint.sentiment_label = sentiment.label
            session.commit()

        return {
            "status": "ok",
            "complaint_id": complaint_id,
            "label": sentiment.label,
        }
    except Exception as exc:
        logger.error(
            "sentiment_task_failed",
            complaint_id=complaint_id,
            error=str(exc),
            retry_count=self.request.retries,
        )
        raise self.retry(exc=exc, countdown=15 * (2**self.request.retries)) from exc
