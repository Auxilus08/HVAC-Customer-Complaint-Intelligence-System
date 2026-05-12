"""SQLAlchemy ORM model for the clusters table."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    label_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fingerprint_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    member_count: Mapped[int | None] = mapped_column(nullable=True)
    centroid: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    avg_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    growth_pct_wow: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_emerging: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cost_exposure_estimate: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    last_run_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    previous_member_ids: Mapped[list[int] | None] = mapped_column(
        ARRAY(BigInteger), nullable=True
    )

    __table_args__ = (
        Index("ix_clusters_is_emerging", "is_emerging"),
        Index("ix_clusters_last_run_id", "last_run_id"),
    )

    @property
    def priority_score(self) -> float:
        """Urgency score for sorting: emerging clusters with worse sentiment rank higher."""
        base = 1.0 if self.is_emerging else 0.0
        sentiment_penalty = abs(min(self.avg_sentiment or 0.0, 0.0))
        growth_boost = min(self.growth_pct_wow or 0.0, 5.0) / 5.0
        return base + sentiment_penalty + growth_boost

    def __repr__(self) -> str:
        return (
            f"<Cluster id={self.id} label={self.label!r} members={self.member_count}>"
        )
