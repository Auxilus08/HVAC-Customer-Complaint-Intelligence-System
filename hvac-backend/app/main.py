"""FastAPI application factory with lifespan, middleware, and routers."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def _warm_cache() -> None:
    """Pre-populate Redis cache on startup so the first dashboard load is hot."""
    try:
        from app.db.session import get_session_factory
        from app.services.cluster_service import list_clusters

        sf = get_session_factory()
        async with sf() as session:
            await list_clusters(session, limit=50)
        logger.info("cache_warmed")
    except Exception as exc:
        logger.warning("cache_warm_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    logger.info("application_starting", env=settings.APP_ENV, debug=settings.APP_DEBUG)

    from app.db.session import init_db

    await init_db()

    import redis.asyncio as aioredis

    try:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await _redis.ping()
        await _redis.aclose()
        logger.info("redis_connected")
    except Exception as exc:
        logger.warning("redis_unavailable", error=str(exc))

    asyncio.create_task(_warm_cache())

    yield

    from app.db.session import close_engine

    await close_engine()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="HVAC Complaint Intelligence System",
        description=(
            "Real-time complaint clustering, sentiment analysis, and "
            "pattern detection for HVAC service operations."
        ),
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # noqa: ANN001
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=rid)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = rid
        return response

    register_exception_handlers(app)

    from app.api.v1.router import v1_router

    app.include_router(v1_router)

    @app.get("/health", tags=["ops"], include_in_schema=False)
    async def health_root() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
