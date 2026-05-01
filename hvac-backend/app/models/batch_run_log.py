"""SQLAlchemy ORM model for the batch_run_log table."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BatchRunLog(Base):
    __tablename__ = "batch_run_log"

    run_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    complaints_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clusters_found: Mapped[int | None] = mapped_column(Integer, nullable=True)
    silhouette_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    noise_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_calls_made: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<BatchRunLog run_id={self.run_id!r} status={self.status!r}>"
