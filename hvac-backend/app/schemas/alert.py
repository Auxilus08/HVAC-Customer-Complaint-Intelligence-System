"""Pydantic v2 schemas for alert responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ALERT_SEVERITY = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
ALERT_TYPE = Literal[
    "emerging_cluster", "sentiment_spike", "volume_surge", "new_sku_pattern"
]


class Alert(BaseModel):
    alert_id: str
    alert_type: ALERT_TYPE
    severity: ALERT_SEVERITY
    cluster_id: int | None
    cluster_label: str | None
    message: str
    complaint_count: int
    growth_pct_wow: float | None
    avg_sentiment: float | None
    product_sku: str | None
    region: str | None
    triggered_at: datetime


class AlertListResponse(BaseModel):
    total: int
    alerts: list[Alert]
