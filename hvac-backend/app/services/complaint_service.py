"""Business logic for complaint ingestion, validation, and queueing."""

from __future__ import annotations

import redis.asyncio as aioredis
from celery import Celery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import encrypt_raw_text, strip_pii
from app.models.complaint import Complaint
from app.schemas.complaint import ComplaintIngest, ComplaintResponse

logger = get_logger(__name__)


async def ingest_complaints(
    payloads: list[ComplaintIngest],
    session: AsyncSession,
    redis_client: aioredis.Redis,
    celery_app: Celery,
) -> tuple[int, int]:
    """Persist complaints and enqueue embedding + sentiment tasks.

    Returns (accepted_count, queued_count).
    PII stripping is applied here — BEFORE any DB write.
    """
    accepted = 0
    queued = 0

    for payload in payloads:
        # ── PII strip BEFORE DB write (rule enforced here) ────────────────────
        clean_text = strip_pii(payload.text)
        raw_encrypted = encrypt_raw_text(payload.text)

        complaint = Complaint(
            clean_text=clean_text,
            raw_text=raw_encrypted,
            source=payload.source,
            region=payload.region,
            product_sku=payload.product_sku,
            customer_id=payload.customer_id,
            technician_id=payload.technician_id,
            external_id=payload.external_id,
            language=payload.language,
            status="pending",
        )
        session.add(complaint)
        await session.flush()  # get auto-assigned id

        logger.info(
            "complaint_ingested",
            complaint_id=complaint.id,
            source=complaint.source,
            region=complaint.region,
        )
        accepted += 1

        # Embed and sentiment write disjoint columns, so they can run in parallel.
        # `chain(...).apply_async()` was previously failing silently on the redis
        # broker — switching to two independent send_task calls is observably reliable.
        celery_app.send_task(
            "app.workers.embedding_worker.embed_complaint",
            args=[complaint.id],
            queue="embeddings",
        )
        celery_app.send_task(
            "app.workers.sentiment_worker.score_sentiment",
            args=[complaint.id],
            queue="sentiment",
        )
        queued += 1

    await session.commit()
    return accepted, queued


async def get_complaint_by_id(
    complaint_id: int, session: AsyncSession
) -> ComplaintResponse | None:
    """Fetch a single complaint by primary key."""
    result = await session.execute(
        select(Complaint).where(Complaint.id == complaint_id)
    )
    complaint = result.scalar_one_or_none()
    if complaint is None:
        return None
    return ComplaintResponse.model_validate(complaint)
