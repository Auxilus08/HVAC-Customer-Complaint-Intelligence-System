"""SQLAlchemy ORM model for the trend_snapshots table."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"

    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id", ondelete="CASCADE"), primary_key=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    complaint_count: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<TrendSnapshot cluster_id={self.cluster_id} date={self.snapshot_date} "
            f"count={self.complaint_count}>"
        )
