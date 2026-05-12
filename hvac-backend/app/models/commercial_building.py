"""SQLAlchemy ORM model for the commercial_buildings reference table."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Double, Integer, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CommercialBuilding(Base):
    __tablename__ = "commercial_buildings"

    building_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    primary_use: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sub_primary_use: Mapped[str | None] = mapped_column(String(80), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_built: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    floors: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    heating_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    country: Mapped[str | None] = mapped_column(String(40), nullable=True)
    lat: Mapped[float | None] = mapped_column(Double, nullable=True)
    lon: Mapped[float | None] = mapped_column(Double, nullable=True)
    eui_kbtu_per_sqft_yr: Mapped[float | None] = mapped_column(Double, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    def __repr__(self) -> str:
        return f"<CommercialBuilding building_id={self.building_id!r} state={self.state!r}>"
