"""Pydantic v2 request/response schemas for complaints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SOURCE_CHOICES = Literal[
    "crm",
    "whatsapp",
    "email",
    "app",
    "field_tech",
    "call_center",
    "nyc_311",
    "cpsc",
    "app_store",
    "synthetic",
    "telegram",
]
SENTIMENT_LABEL_CHOICES = Literal["CRITICAL", "HIGH", "NORMAL", "POSITIVE"]
STATUS_CHOICES = Literal["pending", "embedded", "processed"]


class ComplaintIngest(BaseModel):
    """Payload for a single complaint from any channel."""

    text: str = Field(
        ..., min_length=5, max_length=5000, description="Raw complaint text"
    )
    source: SOURCE_CHOICES
    region: str | None = Field(default=None, max_length=100)
    product_sku: str | None = Field(default=None, max_length=50)
    customer_id: uuid.UUID | None = None
    technician_id: uuid.UUID | None = None
    external_id: str | None = Field(default=None, max_length=128)
    language: str | None = Field(default=None, max_length=8)

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v.strip()


class ComplaintBatchUpload(BaseModel):
    """Batch of complaints ingested from CSV or API."""

    complaints: list[ComplaintIngest] = Field(..., min_length=1, max_length=1000)


class ComplaintResponse(BaseModel):
    """Public representation of a stored complaint."""

    id: int
    clean_text: str
    source: str | None
    region: str | None
    product_sku: str | None
    cluster_id: int | None
    sentiment_score: float | None
    sentiment_label: str | None
    status: str
    created_at: datetime
    embedded_at: datetime | None
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class IngestResponse(BaseModel):
    """Response returned immediately after ingestion (< 100 ms)."""

    accepted: int
    queued_for_embedding: int
    message: str = "Complaints accepted and queued for processing"
