"""SQLAlchemy ORM model for the umap_coords table."""

from __future__ import annotations

from sqlalchemy import BigInteger, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UmapCoord(Base):
    __tablename__ = "umap_coords"

    complaint_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("complaints.id", ondelete="CASCADE"), primary_key=True
    )
    run_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return f"<UmapCoord complaint_id={self.complaint_id} run_id={self.run_id}>"
