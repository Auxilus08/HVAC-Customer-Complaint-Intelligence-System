"""Add image_encrypted + image_mime columns to support_messages.

So the agent dashboard can display the actual photo the customer sent over
Telegram, not just the text extracted from it by vision OCR.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "support_messages",
        sa.Column("image_encrypted", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "support_messages",
        sa.Column("image_mime", sa.String(60), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("support_messages", "image_mime")
    op.drop_column("support_messages", "image_encrypted")
