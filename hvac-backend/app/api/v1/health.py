"""Rich health endpoint with DB / Redis / ML / Gemini sub-checks.

Each check runs in parallel with a 2s timeout and never crashes the
endpoint — failed checks downgrade ``status`` instead of raising.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter
from sqlalchemy import func, select

from app.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.models.batch_run_log import BatchRunLog
from app.models.cluster import Cluster
from app.models.complaint import Complaint

router = APIRouter(tags=["ops"])
logger = get_logger(__name__)

_CHECK_TIMEOUT = 2.0


async def _with_timeout(coro, default: dict[str, Any]) -> dict[str, Any]:
    try:
        return await asyncio.wait_for(coro, timeout=_CHECK_TIMEOUT)
    except asyncio.TimeoutError:
        return {**default, "status": "down", "error": "timeout"}
    except Exception as exc:
        logger.warning("health_check_failed", error=str(exc))
        return {**default, "status": "down", "error": str(exc)[:200]}


async def _db_check() -> dict[str, Any]:
    sf = get_session_factory()
    t0 = time.perf_counter()
    async with sf() as s:
        await s.execute(select(1))
        cnt = (await s.execute(select(func.count()).select_from(Complaint))).scalar_one()
        last_run = (
            await s.execute(
                select(BatchRunLog.completed_at)
                .where(BatchRunLog.status == "completed")
                .order_by(BatchRunLog.completed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    return {
        "status": "ok",
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "complaint_count": int(cnt),
        "last_cluster_run": last_run.isoformat() if last_run else None,
    }


async def _redis_check() -> dict[str, Any]:
    settings = get_settings()
    t0 = time.perf_counter()
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await r.ping()
        embed = await r.llen("celery_embeddings") if await r.exists("celery_embeddings") else 0
        sent = await r.llen("celery_sentiment") if await r.exists("celery_sentiment") else 0
    finally:
        await r.aclose()
    return {
        "status": "ok",
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "embed_queue_depth": int(embed or 0),
        "sentiment_queue_depth": int(sent or 0),
    }


async def _ml_check() -> dict[str, Any]:
    sf = get_session_factory()
    async with sf() as s:
        n = (await s.execute(select(func.count()).select_from(Cluster))).scalar_one()
        run = (
            await s.execute(
                select(BatchRunLog)
                .where(BatchRunLog.status == "completed")
                .order_by(BatchRunLog.completed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    return {
        "status": "ok",
        "clusters_found": int(n or 0),
        "last_silhouette_score": float(run.silhouette_score) if run and run.silhouette_score is not None else None,
        "noise_pct": float(run.noise_pct) * 100 if run and run.noise_pct is not None else None,
    }


async def _gemini_check() -> dict[str, Any]:
    sf = get_session_factory()
    async with sf() as s:
        last_label = (
            await s.execute(
                select(func.max(Cluster.label_updated_at)).where(Cluster.label.is_not(None))
            )
        ).scalar_one_or_none()
    return {
        "status": "ok",
        "last_label_job": last_label.isoformat() if last_label else None,
        "llm_calls_today": None,
    }


@router.get("/health", summary="Rich health check (DB / Redis / ML / Gemini)")
async def health() -> dict[str, Any]:
    settings = get_settings()
    db, redis_, ml, gemini = await asyncio.gather(
        _with_timeout(_db_check(), {"status": "down"}),
        _with_timeout(_redis_check(), {"status": "down"}),
        _with_timeout(_ml_check(), {"status": "down"}),
        _with_timeout(_gemini_check(), {"status": "down"}),
    )
    overall = "ok"
    if db.get("status") != "ok":
        overall = "down"
    elif any(c.get("status") != "ok" for c in (redis_, ml, gemini)):
        overall = "degraded"
    return {
        "status": overall,
        "version": "0.1.0",
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "environment": settings.APP_ENV,
        "checks": {
            "database": db,
            "redis": redis_,
            "ml_pipeline": ml,
            "gemini_api": gemini,
        },
    }
