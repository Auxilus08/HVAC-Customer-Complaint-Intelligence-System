"""Alert generation endpoint — surfaces emerging clusters and sentiment spikes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import DBSessionDep
from app.models.cluster import Cluster
from app.schemas.alert import Alert, AlertListResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])
settings = get_settings()


def _cluster_to_alert(cluster: Cluster) -> Alert:
    severity = "MEDIUM"
    if cluster.avg_sentiment is not None:
        if cluster.avg_sentiment < settings.CRITICAL_SENTIMENT_THRESHOLD:
            severity = "CRITICAL"
        elif cluster.avg_sentiment < -0.3:
            severity = "HIGH"

    return Alert(
        alert_id=str(uuid.uuid4()),
        alert_type="emerging_cluster",
        severity=severity,  # type: ignore[arg-type]
        cluster_id=cluster.id,
        cluster_label=cluster.label,
        message=(
            f"Cluster '{cluster.label or 'Unlabeled'}' is growing fast "
            f"({(cluster.growth_pct_wow or 0)*100:.0f}% WoW, "
            f"{cluster.member_count} complaints)"
        ),
        complaint_count=cluster.member_count or 0,
        growth_pct_wow=cluster.growth_pct_wow,
        avg_sentiment=cluster.avg_sentiment,
        product_sku=None,
        region=None,
        triggered_at=datetime.now(tz=UTC),
    )


@router.get(
    "",
    response_model=AlertListResponse,
    summary="Get active alerts for emerging clusters and sentiment spikes",
)
async def get_alerts(
    session: DBSessionDep,
    severity: str | None = Query(
        default=None, description="Filter by severity: CRITICAL|HIGH|MEDIUM|LOW"
    ),
    limit: int = Query(default=20, ge=1, le=100),
) -> AlertListResponse:
    """Return active alerts derived from the latest clustering run.

    Alerts are generated dynamically from is_emerging clusters and
    CRITICAL-sentiment clusters — no separate alert table needed for MVP.
    """
    q = select(Cluster).where(
        (Cluster.is_emerging == True)  # noqa: E712
        | (Cluster.avg_sentiment < settings.CRITICAL_SENTIMENT_THRESHOLD)
    )

    # Apply severity as a SQL filter BEFORE LIMIT to get correct result counts.
    if severity:
        sev = severity.upper()
        if sev == "CRITICAL":
            q = q.where(
                Cluster.avg_sentiment < settings.CRITICAL_SENTIMENT_THRESHOLD
            )
        elif sev == "HIGH":
            q = q.where(
                Cluster.avg_sentiment >= settings.CRITICAL_SENTIMENT_THRESHOLD,
                Cluster.avg_sentiment < -0.3,
            )
        elif sev == "MEDIUM":
            q = q.where(
                (Cluster.avg_sentiment >= -0.3)
                | (Cluster.avg_sentiment.is_(None))
            )

    q = q.order_by(Cluster.avg_sentiment.asc().nullslast()).limit(limit)

    result = await session.execute(q)
    clusters = result.scalars().all()
    alerts = [_cluster_to_alert(c) for c in clusters]

    return AlertListResponse(total=len(alerts), alerts=alerts)
