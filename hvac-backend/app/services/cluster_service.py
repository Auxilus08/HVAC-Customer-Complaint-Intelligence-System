"""Business logic for querying clusters and computing priority scores."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.cluster import Cluster
from app.models.trend_snapshot import TrendSnapshot
from app.schemas.cluster import (
    ClusterDetail,
    ClusterListResponse,
    ClusterSummary,
    TrendPoint,
)

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
    """Compute a 0–1 urgency score for ranking clusters in the dashboard.

    Higher is more urgent.
    """
    sentiment_component = max(0.0, -(avg_sentiment or 0.0))  # negative = urgent
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
    """Return detailed cluster info including last 14-day trend."""
    result = await session.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if cluster is None:
        return None

    trend_result = await session.execute(
        select(TrendSnapshot)
        .where(TrendSnapshot.cluster_id == cluster_id)
        .order_by(TrendSnapshot.snapshot_date.desc())
        .limit(14)
    )
    trend_rows = trend_result.scalars().all()
    trend = [
        TrendPoint(
            date=str(row.snapshot_date),
            count=row.complaint_count,
            avg_sentiment=row.avg_sentiment,
        )
        for row in reversed(trend_rows)
    ]

    detail = ClusterDetail.model_validate(cluster)
    detail.trend = trend
    return detail
