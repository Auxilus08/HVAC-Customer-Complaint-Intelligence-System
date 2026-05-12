"""Shared scaffolding for all ingest adapters.

IngestBatchContext — async context manager that writes an audit row to ingest_batches.
ChunkedPoster      — POSTs ComplaintIngest dicts to /api/v1/complaints/upload in chunks.
dedupe_existing    — fast DB-side dedup check before posting.
detect_language    — langdetect + Hinglish heuristic.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.models.ingest_batch import IngestBatch

logger = structlog.get_logger(__name__)

# Deterministic langdetect — must be set at module level before any detect() call.
try:
    from langdetect import DetectorFactory
    DetectorFactory.seed = 0
except ImportError:
    pass  # langdetect is a container dep; tolerate absence at import time


@dataclass
class IngestStats:
    fetched: int = 0
    inserted: int = 0
    skipped_dedupe: int = 0
    skipped_validation: int = 0
    errors: int = 0


class IngestBatchContext:
    """Async context manager that creates an `ingest_batches` row at __aenter__,
    updates counters on each method call, and finalizes status to
    'completed' or 'failed' on __aexit__.

    Usage:
        async with IngestBatchContext(source="nyc_311", adapter_version="0.1.0") as batch:
            batch.set_window(start, end)
            batch.add_fetched(n)
            batch.add_inserted(m)
            ...
    """

    def __init__(self, source: str, adapter_version: str = "0.1.0") -> None:
        self.source = source
        self.adapter_version = adapter_version
        self._stats = IngestStats()
        self._batch_id: int | None = None
        self._window_start: datetime | None = None
        self._window_end: datetime | None = None

    async def __aenter__(self) -> "IngestBatchContext":
        factory = get_session_factory()
        async with factory() as session:
            batch = IngestBatch(
                source=self.source,
                adapter_version=self.adapter_version,
                status="running",
            )
            session.add(batch)
            await session.commit()
            await session.refresh(batch)
            self._batch_id = batch.id
        logger.info("ingest_batch_started", batch_id=self._batch_id, source=self.source)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.get(IngestBatch, self._batch_id)
            if result is None:
                return

            if exc_type is None:
                result.status = "completed"
                result.records_fetched = self._stats.fetched
                result.records_inserted = self._stats.inserted
                result.records_skipped_dedupe = self._stats.skipped_dedupe
                result.records_skipped_validation = self._stats.skipped_validation
                result.source_window_start = self._window_start
                result.source_window_end = self._window_end
                result.completed_at = datetime.now(timezone.utc)
                logger.info(
                    "ingest_batch_completed",
                    batch_id=self._batch_id,
                    source=self.source,
                    inserted=self._stats.inserted,
                    skipped_dedupe=self._stats.skipped_dedupe,
                )
            else:
                result.status = "failed"
                result.error_message = str(exc)[:1000]
                result.completed_at = datetime.now(timezone.utc)
                logger.error(
                    "ingest_batch_failed",
                    batch_id=self._batch_id,
                    source=self.source,
                    error=str(exc),
                )

            await session.commit()
        # exception propagates naturally (returning None / not True)

    def set_window(self, start: datetime | None, end: datetime | None) -> None:
        self._window_start = start
        self._window_end = end

    def add_fetched(self, n: int) -> None:
        self._stats.fetched += n

    def add_inserted(self, n: int) -> None:
        self._stats.inserted += n

    def add_skipped_dedupe(self, n: int) -> None:
        self._stats.skipped_dedupe += n

    def add_skipped_validation(self, n: int) -> None:
        self._stats.skipped_validation += n

    @property
    def stats(self) -> IngestStats:
        return self._stats

    @property
    def batch_id(self) -> int | None:
        return self._batch_id


_RETRY_STATUSES = {429, 503}
_MAX_RETRIES = 3
_RETRY_BACKOFF = [1.0, 2.0, 4.0]


class ChunkedPoster:
    """POSTs lists of dicts (matching ComplaintIngest schema) to the local backend
    in chunks. Aggregates IngestResponse counts. Uses httpx async client."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        chunk_size: int = 500,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.chunk_size = chunk_size
        self.timeout = timeout

    async def post(self, complaints: list[dict]) -> tuple[int, int]:
        """POST /api/v1/complaints/upload chunked. Raises on HTTP 5xx, retries 3x on 429/503."""
        url = f"{self.base_url}/api/v1/complaints/upload"
        accepted_total = 0
        queued_total = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for i in range(0, len(complaints), self.chunk_size):
                chunk = complaints[i : i + self.chunk_size]
                payload = {"complaints": chunk}
                last_exc: Exception | None = None

                for attempt in range(_MAX_RETRIES):
                    try:
                        resp = await client.post(url, json=payload)
                        if resp.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES - 1:
                            await asyncio.sleep(_RETRY_BACKOFF[attempt])
                            continue
                        resp.raise_for_status()
                        data = resp.json()
                        accepted_total += data.get("accepted", 0)
                        queued_total += data.get("queued_for_embedding", 0)
                        last_exc = None
                        break
                    except httpx.HTTPStatusError as exc:
                        last_exc = exc
                        if exc.response.status_code not in _RETRY_STATUSES:
                            logger.error(
                                "chunk_post_http_error",
                                status=exc.response.status_code,
                                chunk_start=i,
                            )
                            break
                        if attempt < _MAX_RETRIES - 1:
                            await asyncio.sleep(_RETRY_BACKOFF[attempt])
                    except Exception as exc:
                        last_exc = exc
                        logger.warning("chunk_post_error", error=str(exc), chunk_start=i)
                        break

                if last_exc is not None:
                    logger.warning(
                        "chunk_post_failed_after_retries",
                        chunk_start=i,
                        error=str(last_exc),
                    )

        return accepted_total, queued_total


async def dedupe_existing(
    session: AsyncSession, source: str, external_ids: Iterable[str]
) -> set[str]:
    """Return the subset of external_ids already present in `complaints` for this source.
    Uses `WHERE source = :source AND external_id = ANY(:external_ids)`."""
    ids_list = list(external_ids)
    if not ids_list:
        return set()
    result = await session.execute(
        text(
            "SELECT external_id FROM complaints "
            "WHERE source = :source AND external_id = ANY(:ids)"
        ),
        {"source": source, "ids": ids_list},
    )
    return {row[0] for row in result.fetchall()}


HINGLISH_STEMS = frozenset({
    "thanda", "pareshani", "kharab", "nahi", "hai", "kar",
    "bekaar", "ghatiya", "hota", "raha", "rahi", "kuch", "bahut",
})

# Pre-compiled for whole-word matching
_HINGLISH_RE = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in HINGLISH_STEMS) + r")\b"
)


def detect_language(text: str) -> str:
    """Return ISO-like language tag, or 'und' if undetectable.
    Uses langdetect.detect(); on result == 'en' AND any HINGLISH_STEM
    appears as a whole word in lowercased text, return 'hi-en'.
    Wraps LangDetectException to 'und'."""
    try:
        from langdetect import LangDetectException, detect
        primary = detect(text)
    except ImportError:
        return "und"
    except Exception:
        return "und"

    if primary == "en":
        if _HINGLISH_RE.search(text.lower()):
            return "hi-en"
    return primary
