"""Celery task — encode complaint text into a 384-dim embedding vector.

Delegates ALL embedding logic to ``pipeline.embedder.Embedder`` from hvac-ml.
This worker NEVER instantiates SentenceTransformer directly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from celery import Task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)
settings = get_settings()


class EmbeddingTask(Task):
    """Custom base task with a lazy-loaded Embedder and a per-process sync engine."""

    abstract = True
    _embedder = None
    _session_factory: sessionmaker[Session] | None = None

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
    from app.models.complaint import Complaint

    try:
        with self.session_factory() as session:
            complaint = session.execute(
                select(Complaint).where(Complaint.id == complaint_id)
            ).scalar_one_or_none()

            if complaint is None:
                logger.warning(
                    "embedding_complaint_not_found", complaint_id=complaint_id
                )
                return {"status": "skipped", "reason": "not_found"}

            embedding = self.embedder.encode_single(complaint.clean_text).tolist()
            complaint.embedding = embedding
            complaint.model_version = self.embedder.model_version
            complaint.embedded_at = datetime.now(tz=UTC)
            complaint.status = "embedded"
            session.commit()

        logger.info("embedding_task_completed", complaint_id=complaint_id)
        return {"status": "ok", "complaint_id": complaint_id}
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
