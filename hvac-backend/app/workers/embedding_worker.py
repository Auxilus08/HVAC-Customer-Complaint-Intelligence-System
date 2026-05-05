"""Celery task — encode complaint text into a 384-dim embedding vector.

Delegates ALL embedding logic to ``pipeline.embedder.Embedder`` from hvac-ml.
This worker NEVER instantiates SentenceTransformer directly.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.config import get_settings
from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)
settings = get_settings()


class EmbeddingTask(Task):
    """Custom base task that holds a lazy-loaded Embedder and session factory."""

    abstract = True
    _embedder = None
    _session_factory = None

    @property
    def embedder(self):  # type: ignore[override]
        if self._embedder is None:
            from pipeline.embedder import Embedder

            self._embedder = Embedder(model_name=settings.EMBEDDING_MODEL)
            logger.info(
                "embedder_loaded",
                model=settings.EMBEDDING_MODEL,
                version=self._embedder.model_version,
            )
        return self._embedder

    @property
    def session_factory(self):
        if self._session_factory is None:
            from app.db.session import get_session_factory

            self._session_factory = get_session_factory()
        return self._session_factory


@celery_app.task(
    bind=True,
    base=EmbeddingTask,
    name="app.workers.embedding_worker.embed_complaint",
    max_retries=3,
    default_retry_delay=30,
    queue="embeddings",
)
def embed_complaint(self: EmbeddingTask, complaint_id: int) -> dict:  # type: ignore[misc]
    """Embed a single complaint via the shared Embedder and persist to DB.

    Uses the Embedder's built-in SHA-256 cache as the single source of truth
    for embedding deduplication — no separate Redis embedding cache layer.
    """
    logger.info("embedding_task_started", complaint_id=complaint_id)

    async def _run() -> dict:
        from app.models.complaint import Complaint

        async with self.session_factory() as session:
            result = await session.execute(
                select(Complaint).where(Complaint.id == complaint_id)
            )
            complaint = result.scalar_one_or_none()

            if complaint is None:
                logger.warning(
                    "embedding_complaint_not_found", complaint_id=complaint_id
                )
                return {"status": "skipped", "reason": "not_found"}

            # Single source of truth: hvac-ml Embedder (has built-in cache).
            embedding = self.embedder.encode_single(
                complaint.clean_text
            ).tolist()
            logger.debug("embedding_computed", complaint_id=complaint_id)

            complaint.embedding = embedding
            complaint.model_version = self.embedder.model_version
            complaint.embedded_at = datetime.now(tz=UTC)
            complaint.status = "embedded"
            await session.commit()

        return {"status": "ok", "complaint_id": complaint_id}

    try:
        result = asyncio.run(_run())
        logger.info("embedding_task_completed", complaint_id=complaint_id)
        return result
    except Exception as exc:
        logger.error(
            "embedding_task_failed",
            complaint_id=complaint_id,
            error=str(exc),
            retry_count=self.request.retries,
        )
        raise self.retry(
            exc=exc,
            countdown=30 * (2**self.request.retries),
        ) from exc
