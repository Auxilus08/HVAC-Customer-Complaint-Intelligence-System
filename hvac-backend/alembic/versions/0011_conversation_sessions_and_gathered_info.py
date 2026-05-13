"""Allow multiple support_conversations per Telegram chat + gathered_info.

Two changes:
  1. Drop the unique constraint on support_conversations.telegram_chat_id so
     that each /start command can open a brand new conversation (a fresh
     ticket on the dashboard) while still preserving prior history. Replace
     with a non-unique index for lookups.
  2. Add a JSON column ``gathered_info`` on support_conversations that the
     bot fills with structured facts (model, purchase date, capacity, etc.)
     as the conversation progresses. The dashboard renders these in a
     "Product Information" panel.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the old unique constraint (allow multiple conversations per chat).
    op.drop_constraint(
        "uq_support_conversations_telegram_chat_id",
        "support_conversations",
        type_="unique",
    )
    # Replace with a non-unique B-tree index so lookups by chat_id stay fast.
    op.create_index(
        "ix_support_conversations_telegram_chat_id",
        "support_conversations",
        ["telegram_chat_id"],
    )
    # New JSON column for accumulated product / context facts.
    op.add_column(
        "support_conversations",
        sa.Column("gathered_info", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("support_conversations", "gathered_info")
    op.drop_index(
        "ix_support_conversations_telegram_chat_id",
        table_name="support_conversations",
    )
    op.create_unique_constraint(
        "uq_support_conversations_telegram_chat_id",
        "support_conversations",
        ["telegram_chat_id"],
    )
