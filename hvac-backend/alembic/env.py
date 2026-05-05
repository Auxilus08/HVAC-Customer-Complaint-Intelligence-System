"""Alembic migration environment — sync engine for migrations (psycopg2).

sqlalchemy.url is read from DATABASE_SYNC_URL (or DATABASE_URL with asyncpg
replaced by psycopg2) at runtime — never hardcoded.

The app uses asyncpg at runtime; Alembic always uses a sync psycopg2 engine.
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend root (one level above alembic/).
_env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_env_path)

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import Base and ALL ORM models so autogenerate can detect schema changes.
from app.db.base import Base
from app.models.batch_run_log import BatchRunLog  # noqa: F401
from app.models.cluster import Cluster  # noqa: F401
from app.models.complaint import Complaint  # noqa: F401
from app.models.trend_snapshot import TrendSnapshot  # noqa: F401
from app.models.umap_coord import UmapCoord  # noqa: F401

config = context.config

# ── Inject database URL from environment ──────────────────────────────────────
# Alembic always uses a synchronous driver (psycopg2).
# Strip +asyncpg suffix if present in DATABASE_URL.
_db_url = os.environ.get("DATABASE_SYNC_URL") or os.environ.get(
    "DATABASE_URL", ""
).replace("+asyncpg", "+psycopg2")

if not _db_url:
    raise RuntimeError(
        "DATABASE_SYNC_URL (or DATABASE_URL) environment variable is not set. "
        "Copy .env.example to .env and set the database credentials."
    )

config.set_main_option("sqlalchemy.url", _db_url)

# ── Logging ───────────────────────────────────────────────────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Target metadata ───────────────────────────────────────────────────────────
target_metadata = Base.metadata


# ── Offline mode ─────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode ──────────────────────────────────────────────────────────────
def run_migrations_online() -> None:
    """Apply migrations to the live database using a sync engine."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
