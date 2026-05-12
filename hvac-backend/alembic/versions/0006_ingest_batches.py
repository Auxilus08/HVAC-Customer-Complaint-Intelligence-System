"""Create ingest_batches table for per-adapter run auditing.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingest_batches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="running",
        ),
        sa.Column("records_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "records_skipped_dedupe", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "records_skipped_validation",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("source_window_start", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("source_window_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("adapter_version", sa.String(20), nullable=True),
        sa.CheckConstraint(
            "status IN ('running','completed','failed')",
            name="ck_ingest_batches_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ingest_batches"),
    )
    op.create_index(
        "ix_ingest_batches_source_started",
        "ingest_batches",
        ["source", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingest_batches_source_started", table_name="ingest_batches")
    op.drop_table("ingest_batches")
