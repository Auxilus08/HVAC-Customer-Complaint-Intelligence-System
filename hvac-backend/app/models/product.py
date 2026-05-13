"""SQLAlchemy ORM model for the Carrier product catalog.

Seeded via Alembic data migration 0009 with a curated set of real Carrier
residential + light-commercial HVAC products. Referenced by support
conversations when the LLM matches a customer's description to a SKU.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    family: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tonnage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    seer_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # list[{symptom: str, resolution_tip: str}] — feeds both LLM matching and
    # the AI-resolvable suggestion path. JSON keeps schema flexible.
    common_issues: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        Index("ix_products_family", "family"),
        Index("ix_products_category", "category"),
    )

    def __repr__(self) -> str:
        return f"<Product sku={self.sku} model={self.model_name}>"
