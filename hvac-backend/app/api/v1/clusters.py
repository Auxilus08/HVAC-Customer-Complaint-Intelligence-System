"""Cluster listing and advisory generation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.core.exceptions import ClusterNotFoundError
from app.dependencies import DBSessionDep
from app.schemas.cluster import (
    AdvisoryResponse,
    ClusterChatRequest,
    ClusterChatResponse,
    ClusterDetail,
    ClusterListResponse,
    TrendPoint,
)
from app.services.advisory_service import generate_advisory
from app.services.cluster_chat_service import chat_with_cluster
from app.services.cluster_service import (
    get_cluster_detail,
    get_cluster_trend,
    list_clusters,
)

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get(
    "",
    response_model=ClusterListResponse,
    summary="List all clusters with optional filters",
)
async def get_clusters(
    session: DBSessionDep,
    is_emerging: bool | None = Query(
        default=None, description="Filter to emerging clusters only"
    ),
    run_id: str | None = Query(default=None, description="Filter by batch run ID"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ClusterListResponse:
    """Return paginated cluster list sorted by urgency (emerging first, then sentiment)."""
    return await list_clusters(
        session, is_emerging=is_emerging, run_id=run_id, limit=limit, offset=offset
    )


@router.get(
    "/{cluster_id}",
    response_model=ClusterDetail,
    summary="Get cluster detail including 14-day trend",
)
async def get_cluster(
    cluster_id: int,
    session: DBSessionDep,
) -> ClusterDetail:
    detail = await get_cluster_detail(cluster_id, session)
    if detail is None:
        raise ClusterNotFoundError(f"Cluster {cluster_id} not found")
    return detail


@router.get(
    "/{cluster_id}/trend",
    response_model=list[TrendPoint],
    summary="Daily complaint volume trend for a cluster",
)
async def get_trend(
    cluster_id: int,
    session: DBSessionDep,
    days: int = Query(default=30, ge=1, le=180),
) -> list[TrendPoint]:
    return await get_cluster_trend(cluster_id, session, days=days)


@router.post(
    "/{cluster_id}/chat",
    response_model=ClusterChatResponse,
    summary="Analytics chatbot — converse about a cluster with full context",
)
async def chat_about_cluster(
    cluster_id: int,
    payload: ClusterChatRequest,
    session: DBSessionDep,
) -> ClusterChatResponse:
    """Send a question to the analytics co-pilot.

    The bot is grounded in the cluster's label, member count, sentiment,
    14-day trend, top SKUs/regions, and a handful of PII-redacted sample
    complaints. Prior chat turns are passed in by the client (stateless API).
    """
    try:
        result = await chat_with_cluster(
            session,
            cluster_id=cluster_id,
            history=[turn.model_dump() for turn in payload.history],
            user_message=payload.message,
        )
    except ClusterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ClusterChatResponse(**result)


@router.get(
    "/{cluster_id}/advisory",
    response_model=AdvisoryResponse,
    summary="Generate Gemini-powered technician advisory for a cluster",
)
async def get_advisory(
    cluster_id: int,
    session: DBSessionDep,
) -> AdvisoryResponse:
    """Call Gemini API to produce a diagnostic advisory for field technicians.

    PII stripping is applied to all complaint samples before the API call.
    """
    return await generate_advisory(cluster_id, session)
