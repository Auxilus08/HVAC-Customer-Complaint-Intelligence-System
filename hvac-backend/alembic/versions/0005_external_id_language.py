"""Add external_id and language columns to complaints.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("complaints", sa.Column("external_id", sa.String(128), nullable=True))
    op.add_column("complaints", sa.Column("language", sa.String(8), nullable=True))
    op.execute(
        "CREATE UNIQUE INDEX uq_complaints_source_external_id "
        "ON complaints(source, external_id) WHERE external_id IS NOT NULL"
    )
    op.create_index("ix_complaints_language", "complaints", ["language"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_complaints_source_external_id")
    op.drop_index("ix_complaints_language", table_name="complaints")
    op.drop_column("complaints", "language")
    op.drop_column("complaints", "external_id")
