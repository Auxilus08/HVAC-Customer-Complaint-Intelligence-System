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
    """Return a paginated list of clusters with optional filters.

    Defaults to clusters from the most recent run only. Without this filter the
    table accumulates orphan rows from prior runs (centroids changed → new row
    inserted, old row left behind) and the dashboard floods with stale clusters.
    Callers wanting cross-run history can pass an explicit ``run_id``.
    """
    q = select(Cluster)
    if is_emerging is not None:
        q = q.where(Cluster.is_emerging == is_emerging)
    if run_id is not None:
        q = q.where(Cluster.last_run_id == run_id)
    else:
        # run_id strings sort lexicographically by time (run_YYYYMMDD_HHMMSS_…),
        # so MAX() picks the most recent batch.
        latest_run = (
            select(func.max(Cluster.last_run_id))
            .where(Cluster.last_run_id.is_not(None))
            .scalar_subquery()
        )
        q = q.where(Cluster.last_run_id == latest_run)

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
    """Return ascending-by-date trend points for a cluster, last *days* days.

    Computed on the fly from complaints.created_at so the series reflects the
    actual per-day arrival rate (not the cumulative trend_snapshot member_count,
    which only ticks upward and produces a flat-ish line).
    Days with no complaints are zero-filled so the chart renders a continuous
    30-day x-axis.
    """
    from datetime import date, timedelta

    today = date.today()
    cutoff = today - timedelta(days=days - 1)  # inclusive 30-day window

    rows = (
        await session.execute(
            select(
                func.date(Complaint.created_at).label("day"),
                func.count(Complaint.id).label("cnt"),
                func.avg(Complaint.sentiment_score).label("avg_sent"),
            )
            .where(
                Complaint.cluster_id == cluster_id,
                Complaint.created_at >= cutoff,
            )
            .group_by("day")
        )
    ).all()

    by_day: dict[date, tuple[int, float | None]] = {}
    for day, cnt, avg_sent in rows:
        # func.date() may return a date or an ISO string depending on driver.
        d = day if isinstance(day, date) else date.fromisoformat(str(day))
        by_day[d] = (int(cnt or 0), float(avg_sent) if avg_sent is not None else None)

    series: list[TrendPoint] = []
    for i in range(days):
        d = cutoff + timedelta(days=i)
        cnt, avg_sent = by_day.get(d, (0, None))
        series.append(TrendPoint(date=str(d), count=cnt, avg_sentiment=avg_sent))
    return series
