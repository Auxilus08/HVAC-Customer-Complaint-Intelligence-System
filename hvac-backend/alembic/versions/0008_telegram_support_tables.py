"""Create products + support_conversations + support_messages tables.

Adds Telegram-driven support workflow: a product catalog, per-chat
conversations, and individual messages with PII-redacted text plus
encrypted raw blobs. Also extends the complaints.source CHECK constraint
with the 'telegram' value so escalated conversations can flow into the
existing complaint ingestion pipeline.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── products ──────────────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sku", sa.String(50), nullable=False),
        sa.Column("family", sa.String(80), nullable=True),
        sa.Column("model_name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(80), nullable=True),
        sa.Column("tonnage", sa.String(40), nullable=True),
        sa.Column("seer_rating", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("common_issues", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
    )
    op.create_index("ix_products_family", "products", ["family"])
    op.create_index("ix_products_category", "products", ["category"])

    # ── support_conversations ─────────────────────────────────────────────────
    op.create_table(
        "support_conversations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "customer_display_name_encrypted", sa.LargeBinary(), nullable=True
        ),
        sa.Column("matched_product_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'bot_collecting'"),
        ),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column("complaint_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "last_message_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_support_conversations"),
        sa.UniqueConstraint(
            "telegram_chat_id", name="uq_support_conversations_telegram_chat_id"
        ),
        sa.ForeignKeyConstraint(
            ["matched_product_id"],
            ["products.id"],
            name="fk_support_conversations_matched_product_id_products",
        ),
        sa.ForeignKeyConstraint(
            ["complaint_id"],
            ["complaints.id"],
            name="fk_support_conversations_complaint_id_complaints",
        ),
        sa.CheckConstraint(
            "status IN ('bot_collecting','bot_resolved','escalated','agent_active','closed')",
            name="ck_support_conversations_status",
        ),
    )
    op.create_index(
        "ix_support_conversations_status", "support_conversations", ["status"]
    )
    op.create_index(
        "ix_support_conversations_last_message_at",
        "support_conversations",
        ["last_message_at"],
    )

    # ── support_messages ──────────────────────────────────────────────────────
    op.create_table(
        "support_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("body_redacted", sa.Text(), nullable=False),
        sa.Column("body_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("llm_metadata", sa.JSON(), nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_support_messages"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["support_conversations.id"],
            name="fk_support_messages_conversation_id_support_conversations",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "direction IN ('inbound','outbound_bot','outbound_agent')",
            name="ck_support_messages_direction",
        ),
    )
    op.create_index(
        "ix_support_messages_conversation_id_created_at",
        "support_messages",
        ["conversation_id", "created_at"],
    )

    # ── extend complaints.source CHECK to include 'telegram' ──────────────────
    op.execute("ALTER TABLE complaints DROP CONSTRAINT IF EXISTS ck_complaints_source")
    op.execute(
        "ALTER TABLE complaints ADD CONSTRAINT ck_complaints_source "
        "CHECK (source IN ("
        "'crm','whatsapp','email','app','field_tech','call_center',"
        "'nyc_311','cpsc','app_store','synthetic','telegram'"
        "))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE complaints DROP CONSTRAINT IF EXISTS ck_complaints_source")
    op.execute(
        "ALTER TABLE complaints ADD CONSTRAINT ck_complaints_source "
        "CHECK (source IN ("
        "'crm','whatsapp','email','app','field_tech','call_center',"
        "'nyc_311','cpsc','app_store','synthetic'"
        "))"
    )

    op.drop_index(
        "ix_support_messages_conversation_id_created_at",
        table_name="support_messages",
    )
    op.drop_table("support_messages")

    op.drop_index(
        "ix_support_conversations_last_message_at",
        table_name="support_conversations",
    )
    op.drop_index(
        "ix_support_conversations_status", table_name="support_conversations"
    )
    op.drop_table("support_conversations")

    op.drop_index("ix_products_category", table_name="products")
    op.drop_index("ix_products_family", table_name="products")
    op.drop_table("products")
