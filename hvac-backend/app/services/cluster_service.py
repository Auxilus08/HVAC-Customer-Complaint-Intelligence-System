"""Business logic for querying clusters and computing priority scores."""

from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.cluster import Cluster
from app.models.complaint import Complaint
from app.models.trend_snapshot import TrendSnapshot
from app.schemas.cluster import (
    ClusterDetail,
    ClusterListResponse,
    ClusterSummary,
    TrendPoint,
)
from app.schemas.complaint import ComplaintResponse

logger = get_logger(__name__)

# Priority score weights
_W_SENTIMENT = 0.4
_W_GROWTH = 0.35
_W_VOLUME = 0.25


def compute_priority_score(
    avg_sentiment: float | None,
    growth_pct_wow: float | None,
    member_count: int | None,
    max_member_count: int = 1,
) -> float:
    """Compute a 0–1 urgency score for ranking clusters in the dashboard."""
    sentiment_component = max(0.0, -(avg_sentiment or 0.0))
    growth_component = min(1.0, max(0.0, (growth_pct_wow or 0.0) / 2.0))
    volume_component = min(1.0, (member_count or 0) / max(max_member_count, 1))

    return (
        _W_SENTIMENT * sentiment_component
        + _W_GROWTH * growth_component
        + _W_VOLUME * volume_component
    )


async def list_clusters(
    session: AsyncSession,
    is_emerging: bool | None = None,
    run_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ClusterListResponse:
    """Return a paginated list of clusters with optional filters."""
    q = select(Cluster)
    if is_emerging is not None:
        q = q.where(Cluster.is_emerging == is_emerging)
    if run_id is not None:
        q = q.where(Cluster.last_run_id == run_id)

    count_result = await session.execute(select(func.count()).select_from(q.subquery()))
    total: int = count_result.scalar_one()

    q = (
        q.order_by(Cluster.is_emerging.desc(), Cluster.avg_sentiment.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(q)
    clusters = result.scalars().all()

    return ClusterListResponse(
        total=total,
        clusters=[ClusterSummary.model_validate(c) for c in clusters],
    )


async def get_cluster_detail(
    cluster_id: int, session: AsyncSession
) -> ClusterDetail | None:
    """Return detailed cluster info including 14-day trend, top SKUs / regions
    and the 10 most recent complaints assigned to the cluster."""
    cluster = (
        await session.execute(select(Cluster).where(Cluster.id == cluster_id))
    ).scalar_one_or_none()
    if cluster is None:
        return None

    # ── 14-day trend snapshot ──────────────────────────────────────────────
    trend_rows = (
        await session.execute(
            select(TrendSnapshot)
            .where(TrendSnapshot.cluster_id == cluster_id)
            .order_by(TrendSnapshot.snapshot_date.desc())
            .limit(14)
        )
    ).scalars().all()
    trend = [
        TrendPoint(
            date=str(row.snapshot_date),
            count=row.complaint_count,
            avg_sentiment=row.avg_sentiment,
        )
        for row in reversed(trend_rows)
    ]

    # ── Top 3 SKUs ────────────────────────────────────────────────────────
    sku_rows = (
        await session.execute(
            select(Complaint.product_sku, func.count(Complaint.id).label("cnt"))
            .where(
                Complaint.cluster_id == cluster_id,
                Complaint.product_sku.is_not(None),
            )
            .group_by(Complaint.product_sku)
            .order_by(desc("cnt"))
            .limit(3)
        )
    ).all()
    top_skus = [r[0] for r in sku_rows]

    # ── Top 3 regions ─────────────────────────────────────────────────────
    region_rows = (
        await session.execute(
            select(Complaint.region, func.count(Complaint.id).label("cnt"))
            .where(
                Complaint.cluster_id == cluster_id,
                Complaint.region.is_not(None),
            )
            .group_by(Complaint.region)
            .order_by(desc("cnt"))
            .limit(3)
        )
    ).all()
    top_regions = [r[0] for r in region_rows]

    # ── 10 most recent complaints ─────────────────────────────────────────
    recent_rows = (
        await session.execute(
            select(Complaint)
            .where(Complaint.cluster_id == cluster_id)
            .order_by(Complaint.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    recent_complaints = [ComplaintResponse.model_validate(c) for c in recent_rows]

    detail = ClusterDetail.model_validate(cluster)
    detail.trend = trend
    detail.top_skus = top_skus
    detail.top_regions = top_regions
    detail.recent_complaints = recent_complaints
    return detail


async def get_cluster_trend(
    cluster_id: int, session: AsyncSession, days: int = 30
) -> list[TrendPoint]:
    """Return ascending-by-date trend points for a cluster, last *days* days."""
    from datetime import date, timedelta

    cutoff = date.today() - timedelta(days=days)
    rows = (
        await session.execute(
            select(TrendSnapshot)
            .where(
                TrendSnapshot.cluster_id == cluster_id,
                TrendSnapshot.snapshot_date >= cutoff,
            )
            .order_by(TrendSnapshot.snapshot_date.asc())
        )
    ).scalars().all()
    return [
        TrendPoint(
            date=str(r.snapshot_date),
            count=r.complaint_count,
            avg_sentiment=r.avg_sentiment,
        )
        for r in rows
    ]
