"""SQLAlchemy ORM model for individual messages within a support conversation."""

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

# Direction enum values
MESSAGE_DIRECTIONS = ("inbound", "outbound_bot", "outbound_agent")


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("support_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    body_redacted: Mapped[str] = mapped_column(Text, nullable=False)
    body_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    llm_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Photo attachments — stored as encrypted bytes so the agent can review what
    # the customer actually sent without us having to host a separate file store.
    image_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    image_mime: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        Index(
            "ix_support_messages_conversation_id_created_at",
            "conversation_id",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SupportMessage id={self.id} conv={self.conversation_id} "
            f"dir={self.direction}>"
        )
