"""FastAPI dependency providers for DB session, Redis client, and Celery app."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import redis.asyncio as aioredis
from celery import Celery
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_db_session

# ── Type aliases ──────────────────────────────────────────────────────────────

SettingsDep = Annotated[Settings, Depends(get_settings)]


# ── DB ────────────────────────────────────────────────────────────────────────


async def db_session_dep() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


DBSessionDep = Annotated[AsyncSession, Depends(db_session_dep)]


# ── Redis ─────────────────────────────────────────────────────────────────────

_redis_pool: aioredis.Redis | None = None


async def get_redis(settings: SettingsDep) -> aioredis.Redis:
    """Return a shared async Redis client."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]


# ── Celery ────────────────────────────────────────────────────────────────────


def get_celery_app(settings: SettingsDep) -> Celery:
    """Return the Celery app — imported lazily to avoid circular imports."""
    from app.workers.celery_app import create_celery_app

    return create_celery_app(settings)


CeleryDep = Annotated[Celery, Depends(get_celery_app)]
