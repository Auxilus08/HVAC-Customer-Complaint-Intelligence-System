"""FastAPI application factory with lifespan, CORS, and middleware."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle startup and shutdown events."""
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)

    logger.info(
        "application_starting",
        env=settings.APP_ENV,
        debug=settings.APP_DEBUG,
    )

    from app.db.session import init_db

    await init_db()

    import redis.asyncio as aioredis

    try:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await _redis.ping()
        await _redis.close()
        logger.info("redis_connected")
    except Exception as exc:
        logger.warning("redis_unavailable", error=str(exc))

    yield

    from app.db.session import close_engine

    await close_engine()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
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

    # ── Middleware ─────────────────────────────────────────────────────────────
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    from app.api.v1.router import v1_router

    app.include_router(v1_router)

    @app.get("/health", tags=["ops"], include_in_schema=False)
    async def health_root() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/health", tags=["ops"], include_in_schema=False)
    async def health_v1() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
