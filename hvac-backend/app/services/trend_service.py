"""Week-over-week growth calculation and trend snapshot utilities."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.complaint import Complaint
from app.models.trend_snapshot import TrendSnapshot

logger = get_logger(__name__)


async def compute_wow_growth(cluster_id: int, session: AsyncSession) -> float | None:
    """Calculate week-over-week complaint volume growth for a cluster.

    Returns growth as a decimal fraction (0.5 = 50% growth).
    Returns None if insufficient history.
    """
    today = date.today()
    current_week_start = today - timedelta(days=7)
    prev_week_start = today - timedelta(days=14)

    current_result = await session.execute(
        select(func.count(Complaint.id)).where(
            Complaint.cluster_id == cluster_id,
            Complaint.created_at >= current_week_start,
            Complaint.created_at < today,
        )
    )
    current_count: int = current_result.scalar_one()

    prev_result = await session.execute(
        select(func.count(Complaint.id)).where(
            Complaint.cluster_id == cluster_id,
            Complaint.created_at >= prev_week_start,
            Complaint.created_at < current_week_start,
        )
    )
    prev_count: int = prev_result.scalar_one()

    if prev_count == 0:
        return None

    return (current_count - prev_count) / prev_count


async def upsert_trend_snapshot(
    cluster_id: int,
    snapshot_date: date,
    complaint_count: int,
    avg_sentiment: float | None,
    session: AsyncSession,
) -> None:
    """Insert or update a daily trend snapshot for a cluster."""
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(TrendSnapshot).values(
        cluster_id=cluster_id,
        snapshot_date=snapshot_date,
        complaint_count=complaint_count,
        avg_sentiment=avg_sentiment,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["cluster_id", "snapshot_date"],
        set_={
            "complaint_count": complaint_count,
            "avg_sentiment": avg_sentiment,
        },
    )
    await session.execute(stmt)
    await session.commit()

    logger.debug(
        "trend_snapshot_upserted",
        cluster_id=cluster_id,
        date=str(snapshot_date),
        count=complaint_count,
    )
