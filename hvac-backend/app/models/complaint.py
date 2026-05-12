"""SQLAlchemy ORM model for the complaints table."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    Index,
    LargeBinary,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    clean_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_sku: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    technician_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cluster_id: Mapped[int | None] = mapped_column(nullable=True)
    hdbscan_conf: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    embedded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index(
            "ix_complaints_embedding_ivfflat",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_complaints_status", "status"),
        Index("ix_complaints_cluster_id", "cluster_id"),
        Index("ix_complaints_created_at", "created_at"),
        Index("ix_complaints_source", "source"),
        Index("ix_complaints_product_sku", "product_sku"),
        Index("ix_complaints_region", "region"),
    )

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Complaint:
        """Construct a Complaint from a CSV row dict (pre-PII-stripped text)."""
        return cls(
            clean_text=row.get("complaint_text") or row.get("text", ""),
            source=row.get("source") or None,
            region=row.get("region") or None,
            product_sku=row.get("product_sku") or None,
            status="pending",
        )

    def __repr__(self) -> str:
        return f"<Complaint id={self.id} source={self.source} status={self.status}>"
