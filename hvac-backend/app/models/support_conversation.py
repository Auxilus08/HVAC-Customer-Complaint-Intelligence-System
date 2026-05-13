"""SQLAlchemy ORM model for Telegram-driven customer support conversations.

One row per Telegram chat. Tracks status, matched product, and the linked
Complaint row created on escalation (so escalated conversations flow into
the existing embedding → clustering → sentiment pipeline).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Status values — enforced at application layer (Pydantic), not DB enum,
# to keep migrations cheap as states evolve.
CONVERSATION_STATUSES = (
    "bot_collecting",  # bot is still gathering info / answering follow-ups
    "bot_resolved",    # bot's AI suggestion was accepted (or customer left)
    "escalated",       # flagged for human; ticket open
    "agent_active",    # a human agent has replied at least once
    "closed",          # resolved (by bot or agent), no further action
)


class SupportConversation(Base):
    __tablename__ = "support_conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Not unique: each /start command opens a fresh conversation (ticket) for
    # the same Telegram chat. Lookups still hit a non-unique index.
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    customer_display_name_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    matched_product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="bot_collecting"
    )
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    complaint_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("complaints.id"), nullable=True
    )
    # Structured facts the bot has accumulated about the customer's product
    # over the course of the conversation — model, purchase date, capacity,
    # symptom summary, etc. Rendered as a "Product Information" panel in the
    # agent dashboard.
    gathered_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        Index("ix_support_conversations_status", "status"),
        Index("ix_support_conversations_last_message_at", "last_message_at"),
        Index("ix_support_conversations_telegram_chat_id", "telegram_chat_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<SupportConversation id={self.id} chat={self.telegram_chat_id} "
            f"status={self.status}>"
        )
