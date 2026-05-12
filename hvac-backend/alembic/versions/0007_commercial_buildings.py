"""Create commercial_buildings reference table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commercial_buildings",
        sa.Column("building_id", sa.String(64), nullable=False),
        sa.Column("site_id", sa.String(32), nullable=True),
        sa.Column("primary_use", sa.String(80), nullable=True),
        sa.Column("sub_primary_use", sa.String(80), nullable=True),
        sa.Column("industry", sa.String(80), nullable=True),
        sa.Column("sqft", sa.Integer(), nullable=True),
        sa.Column("year_built", sa.SmallInteger(), nullable=True),
        sa.Column("floors", sa.SmallInteger(), nullable=True),
        sa.Column("heating_type", sa.String(40), nullable=True),
        sa.Column("state", sa.String(40), nullable=True),
        sa.Column("country", sa.String(40), nullable=True),
        sa.Column("lat", sa.Double(), nullable=True),
        sa.Column("lon", sa.Double(), nullable=True),
        sa.Column("eui_kbtu_per_sqft_yr", sa.Double(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("building_id", name="pk_commercial_buildings"),
    )
    op.create_index(
        "ix_commercial_buildings_primary_use",
        "commercial_buildings",
        ["primary_use"],
    )
    op.create_index(
        "ix_commercial_buildings_state",
        "commercial_buildings",
        ["state"],
    )


def downgrade() -> None:
    op.drop_index("ix_commercial_buildings_state", table_name="commercial_buildings")
    op.drop_index(
        "ix_commercial_buildings_primary_use", table_name="commercial_buildings"
    )
    op.drop_table("commercial_buildings")
