"""Initial schema — all 5 tables + pgvector extension.

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── pgvector extension ────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── complaints ────────────────────────────────────────────────────────────
    op.create_table(
        "complaints",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("clean_text", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.LargeBinary(), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("product_sku", sa.String(50), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("technician_id", sa.Uuid(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("model_version", sa.String(20), nullable=True),
        sa.Column("cluster_id", sa.Integer(), nullable=True),
        sa.Column("hdbscan_conf", sa.Float(), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("sentiment_label", sa.String(20), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("embedded_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source IN ('crm','whatsapp','email','app','field_tech','call_center')",
            name="ck_complaints_source",
        ),
        sa.CheckConstraint(
            "status IN ('pending','embedded','processed')",
            name="ck_complaints_status",
        ),
        sa.CheckConstraint(
            "sentiment_label IN ('CRITICAL','HIGH','NORMAL','POSITIVE') OR sentiment_label IS NULL",
            name="ck_complaints_sentiment_label",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_complaints"),
    )

    # Indexes on complaints
    op.create_index("ix_complaints_status", "complaints", ["status"])
    op.create_index("ix_complaints_cluster_id", "complaints", ["cluster_id"])
    op.create_index("ix_complaints_created_at", "complaints", ["created_at"])
    op.create_index("ix_complaints_source", "complaints", ["source"])
    op.create_index("ix_complaints_product_sku", "complaints", ["product_sku"])
    op.create_index("ix_complaints_region", "complaints", ["region"])

    # IVFFlat index on the embedding vector (cosine distance)
    # lists=100 is appropriate for ~100k-1M rows; tune for larger datasets
    op.execute(
        """
        CREATE INDEX ix_complaints_embedding_ivfflat
        ON complaints
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )

    # ── clusters ──────────────────────────────────────────────────────────────
    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("label_updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("fingerprint_hash", sa.String(64), nullable=True),
        sa.Column("member_count", sa.Integer(), nullable=True),
        sa.Column("centroid", Vector(384), nullable=True),
        sa.Column("avg_sentiment", sa.Float(), nullable=True),
        sa.Column("growth_pct_wow", sa.Float(), nullable=True),
        sa.Column("is_emerging", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("cost_exposure_estimate", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("last_run_id", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_clusters"),
    )

    op.create_index("ix_clusters_is_emerging", "clusters", ["is_emerging"])
    op.create_index("ix_clusters_last_run_id", "clusters", ["last_run_id"])

    # ── umap_coords ───────────────────────────────────────────────────────────
    op.create_table(
        "umap_coords",
        sa.Column("complaint_id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.String(50), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["complaint_id"],
            ["complaints.id"],
            name="fk_umap_coords_complaint_id_complaints",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("complaint_id", "run_id", name="pk_umap_coords"),
    )

    op.create_index("ix_umap_coords_run_id", "umap_coords", ["run_id"])

    # ── trend_snapshots ───────────────────────────────────────────────────────
    op.create_table(
        "trend_snapshots",
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("complaint_count", sa.Integer(), nullable=False),
        sa.Column("avg_sentiment", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["clusters.id"],
            name="fk_trend_snapshots_cluster_id_clusters",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "cluster_id", "snapshot_date", name="pk_trend_snapshots"
        ),
    )

    op.create_index(
        "ix_trend_snapshots_snapshot_date", "trend_snapshots", ["snapshot_date"]
    )

    # ── batch_run_log ─────────────────────────────────────────────────────────
    op.create_table(
        "batch_run_log",
        sa.Column("run_id", sa.String(50), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=True),
        sa.Column("complaints_processed", sa.Integer(), nullable=True),
        sa.Column("clusters_found", sa.Integer(), nullable=True),
        sa.Column("silhouette_score", sa.Float(), nullable=True),
        sa.Column("noise_pct", sa.Float(), nullable=True),
        sa.Column("llm_calls_made", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("run_id", name="pk_batch_run_log"),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("batch_run_log")
    op.drop_table("trend_snapshots")
    op.drop_table("umap_coords")
    op.drop_table("clusters")
    op.drop_index("ix_complaints_embedding_ivfflat", table_name="complaints")
    op.drop_index("ix_complaints_region", table_name="complaints")
    op.drop_index("ix_complaints_product_sku", table_name="complaints")
    op.drop_index("ix_complaints_source", table_name="complaints")
    op.drop_index("ix_complaints_created_at", table_name="complaints")
    op.drop_index("ix_complaints_cluster_id", table_name="complaints")
    op.drop_index("ix_complaints_status", table_name="complaints")
    op.drop_table("complaints")
    op.execute("DROP EXTENSION IF EXISTS vector")
