"""pytest fixtures — test DB (PostgreSQL), async test client, mock Redis.

Each test gets its own event loop and engine to avoid cross-scope asyncio
issues with asyncpg on Python 3.14. Schema setup uses a synchronous
psycopg2 connection so it runs once without touching the async pool.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.main import create_app

_TEST_ASYNC_URL = (
    "postgresql+asyncpg://hvac_user:change_me_in_production@localhost:5432/hvac_test"
)
_TRUNCATE_SQL = (
    "TRUNCATE TABLE complaints, clusters, umap_coords, trend_snapshots, "
    "batch_run_log, support_messages, support_conversations, products "
    "RESTART IDENTITY CASCADE"
)


def _sync_setup_schema() -> None:
    """Create pgvector extension and all tables synchronously (once per session)."""
    import sqlalchemy as sa

    from app.models import (  # noqa: F401 — registers models on Base.metadata
        BatchRunLog,
        Cluster,
        Complaint,
        Product,
        SupportConversation,
        SupportMessage,
        TrendSnapshot,
        UmapCoord,
    )

    sync_url = "postgresql+psycopg2://hvac_user:change_me_in_production@localhost:5432/hvac_test"
    engine = sa.create_engine(sync_url)
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
    engine.dispose()


# Create schema once before any test in the session
_sync_setup_schema()


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(_TEST_ASYNC_URL, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.execute(text(_TRUNCATE_SQL))
    factory = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session


# ── Mock Redis ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_redis() -> MagicMock:
    redis = MagicMock()
    redis.get = MagicMock(return_value=None)
    redis.setex = MagicMock()
    redis.ping = AsyncMock(return_value=True)
    return redis


# ── Mock Celery ───────────────────────────────────────────────────────────────


@pytest.fixture
def mock_celery() -> MagicMock:
    celery = MagicMock()
    celery.send_task = MagicMock()
    return celery


# ── Test HTTP client ──────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(
    test_session: AsyncSession,
    mock_redis: MagicMock,
    mock_celery: MagicMock,
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    from app import dependencies

    app.dependency_overrides[dependencies.db_session_dep] = lambda: test_session  # type: ignore[assignment]
    app.dependency_overrides[dependencies.get_redis] = lambda: mock_redis
    app.dependency_overrides[dependencies.get_celery_app] = lambda: mock_celery

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac
