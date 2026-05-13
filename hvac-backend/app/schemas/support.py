"""Pydantic v2 schemas for the Telegram-driven support workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ConversationStatus = Literal[
    "bot_collecting",
    "bot_resolved",
    "escalated",
    "agent_active",
    "closed",
]
MessageDirection = Literal["inbound", "outbound_bot", "outbound_agent"]


class ProductSummary(BaseModel):
    id: int
    sku: str
    family: str | None
    model_name: str
    category: str | None
    tonnage: str | None

    model_config = {"from_attributes": True}


class SupportMessageOut(BaseModel):
    """Single message — always PII-redacted; raw text is encrypted-only."""

    id: int
    direction: MessageDirection
    body: str = Field(..., description="PII-redacted message body, safe for display")
    llm_metadata: dict | None = None
    has_image: bool = Field(
        default=False,
        description=(
            "True when the customer attached a photo. The agent dashboard "
            "can fetch the actual image bytes from "
            "GET /api/v1/support/messages/{id}/image"
        ),
    )
    image_mime: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_row(cls, row) -> SupportMessageOut:
        return cls(
            id=row.id,
            direction=row.direction,
            body=row.body_redacted,
            llm_metadata=row.llm_metadata,
            has_image=bool(getattr(row, "image_encrypted", None)),
            image_mime=getattr(row, "image_mime", None),
            created_at=row.created_at,
        )


class SupportTicketSummary(BaseModel):
    """List-view row: enough info for the inbox table."""

    id: int
    status: ConversationStatus
    matched_product: ProductSummary | None = None
    last_message_preview: str | None = None
    last_message_direction: MessageDirection | None = None
    message_count: int
    created_at: datetime
    last_message_at: datetime


class SupportTicketDetail(BaseModel):
    """Detail view: full thread + product + conversation metadata."""

    id: int
    status: ConversationStatus
    matched_product: ProductSummary | None = None
    escalation_reason: str | None = None
    complaint_id: int | None = None
    customer_display_name: str | None = Field(
        default=None,
        description="Decrypted display name when present; otherwise None.",
    )
    gathered_info: dict | None = Field(
        default=None,
        description=(
            "Structured facts about the customer's product accumulated over "
            "the conversation. Rendered as a 'Product Information' panel "
            "in the agent dashboard."
        ),
    )
    created_at: datetime
    last_message_at: datetime
    messages: list[SupportMessageOut]


class AgentReplyIn(BaseModel):
    """Body for POST /support/tickets/{id}/reply."""

    text: str = Field(..., min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("text must not be blank")
        return cleaned


class TicketListResponse(BaseModel):
    tickets: list[SupportTicketSummary]
    total: int
