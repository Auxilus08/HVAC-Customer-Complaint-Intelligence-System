"""Add performance indexes for dashboard query hotpaths.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-05
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_complaints_cluster_id_partial "
        "ON complaints(cluster_id) WHERE cluster_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_complaints_created_at_cluster "
        "ON complaints(created_at, cluster_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_clusters_is_emerging_partial "
        "ON clusters(is_emerging) WHERE is_emerging = TRUE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_complaints_status_pending "
        "ON complaints(status) WHERE status = 'pending'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_complaints_sentiment_label "
        "ON complaints(sentiment_label)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_complaints_cluster_id_partial")
    op.execute("DROP INDEX IF EXISTS idx_complaints_created_at_cluster")
    op.execute("DROP INDEX IF EXISTS idx_clusters_is_emerging_partial")
    op.execute("DROP INDEX IF EXISTS idx_complaints_status_pending")
    op.execute("DROP INDEX IF EXISTS idx_complaints_sentiment_label")
