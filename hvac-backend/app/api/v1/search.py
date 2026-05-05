"""Complaint search endpoint with text + filter support."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.logging import get_logger
from app.dependencies import DBSessionDep
from app.models.complaint import Complaint
from app.schemas.complaint import ComplaintResponse

router = APIRouter(prefix="/complaints", tags=["complaints"])
logger = get_logger(__name__)


@router.get("/search", summary="Search and filter complaints")
async def search_complaints(
    session: DBSessionDep,
    q: str | None = Query(default=None, description="Text search on clean_text"),
    cluster_id: int | None = Query(default=None),
    region: str | None = Query(default=None),
    sku: str | None = Query(default=None, alias="sku"),
    sentiment: str | None = Query(default=None, pattern="^(CRITICAL|HIGH|NORMAL|POSITIVE)$"),
    source: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Build a filtered query, return paginated results plus a total count."""
    base = select(Complaint)

    filters = []
    if q:
        filters.append(Complaint.clean_text.ilike(f"%{q}%"))
    if cluster_id is not None:
        filters.append(Complaint.cluster_id == cluster_id)
    if region:
        filters.append(Complaint.region == region)
    if sku:
        filters.append(Complaint.product_sku == sku)
    if sentiment:
        filters.append(Complaint.sentiment_label == sentiment)
    if source:
        filters.append(Complaint.source == source)
    if from_date:
        filters.append(Complaint.created_at >= from_date)
    if to_date:
        filters.append(Complaint.created_at <= to_date)

    for f in filters:
        base = base.where(f)

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    rows = (
        await session.execute(
            base.order_by(Complaint.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()

    items = [ComplaintResponse.model_validate(c) for c in rows]
    return {
        "complaints": items,
        "total": int(total),
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < int(total),
    }
