"""UMAP coordinate retrieval endpoint for scatter visualisation."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DBSessionDep
from app.models.batch_run_log import BatchRunLog
from app.models.complaint import Complaint
from app.models.umap_coord import UmapCoord

router = APIRouter(prefix="/umap", tags=["umap"])


class UmapPoint(BaseModel):
    complaint_id: int
    x: float
    y: float
    cluster_id: int | None
    sentiment_label: str | None
    source: str | None
    product_sku: str | None
    region: str | None


class UmapResponse(BaseModel):
    run_id: str
    point_count: int
    points: list[UmapPoint]


async def _resolve_run_id(run_id: str | None, session: AsyncSession) -> str | None:
    """Resolve 'latest' to the most recent completed run_id."""
    if run_id is None or run_id == "latest":
        result = await session.execute(
            select(BatchRunLog.run_id)
            .where(BatchRunLog.status == "completed")
            .order_by(BatchRunLog.completed_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row
    return run_id


@router.get(
    "",
    response_model=UmapResponse,
    summary="Get 2D UMAP coordinates for scatter plot visualisation",
)
async def get_umap(
    session: DBSessionDep,
    run_id: str | None = Query(
        default="latest", description="Batch run ID or 'latest'"
    ),
    cluster_id: int | None = Query(
        default=None, description="Filter to a single cluster"
    ),
) -> UmapResponse:
    """Return x/y coordinates from the most recent (or specified) UMAP 2D run.

    These coordinates are pre-computed — never recomputed on demand.
    """
    resolved_run_id = await _resolve_run_id(run_id, session)
    if resolved_run_id is None:
        return UmapResponse(run_id="none", point_count=0, points=[])

    q = (
        select(
            UmapCoord.complaint_id,
            UmapCoord.x,
            UmapCoord.y,
            Complaint.cluster_id,
            Complaint.sentiment_label,
            Complaint.source,
            Complaint.product_sku,
            Complaint.region,
        )
        .join(Complaint, Complaint.id == UmapCoord.complaint_id)
        .where(UmapCoord.run_id == resolved_run_id)
    )

    if cluster_id is not None:
        q = q.where(Complaint.cluster_id == cluster_id)

    result = await session.execute(q)
    rows = result.fetchall()

    points = [
        UmapPoint(
            complaint_id=r[0],
            x=r[1],
            y=r[2],
            cluster_id=r[3],
            sentiment_label=r[4],
            source=r[5],
            product_sku=r[6],
            region=r[7],
        )
        for r in rows
    ]

    return UmapResponse(run_id=resolved_run_id, point_count=len(points), points=points)
