"""Pydantic v2 schemas for cluster responses."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.complaint import ComplaintResponse


class TrendPoint(BaseModel):
    date: str
    count: int
    avg_sentiment: float | None


class ClusterSummary(BaseModel):
    id: int
    label: str | None
    member_count: int | None
    avg_sentiment: float | None
    growth_pct_wow: float | None
    is_emerging: bool
    cost_exposure_estimate: Decimal | None
    last_run_id: str | None

    model_config = {"from_attributes": True}


class ClusterDetail(BaseModel):
    id: int
    label: str | None
    label_updated_at: datetime | None
    fingerprint_hash: str | None
    member_count: int | None
    avg_sentiment: float | None
    growth_pct_wow: float | None
    is_emerging: bool
    cost_exposure_estimate: Decimal | None
    created_at: datetime
    last_run_id: str | None
    trend: list[TrendPoint] = Field(default_factory=list)
    top_skus: list[str] = Field(default_factory=list)
    top_regions: list[str] = Field(default_factory=list)
    recent_complaints: list[ComplaintResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AdvisoryResponse(BaseModel):
    cluster_id: int
    label: str | None
    advisory_text: str
    generated_at: datetime


class ClusterListResponse(BaseModel):
    total: int
    clusters: list[ClusterSummary]


class ChatTurn(BaseModel):
    """One previous message in the analytics chatbot session."""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=8000)


class ClusterChatRequest(BaseModel):
    """POST body for /clusters/{id}/chat — analyst question + prior turns."""

    message: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=40)


class ClusterChatResponse(BaseModel):
    cluster_id: int
    reply: str
    generated_at: datetime
    model: str
