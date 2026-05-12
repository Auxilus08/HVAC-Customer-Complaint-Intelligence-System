"""Complaint ingestion and retrieval endpoints."""

from __future__ import annotations

import csv
import io
import json
import random
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy import select

from app.core.exceptions import ComplaintNotFoundError
from app.dependencies import CeleryDep, DBSessionDep, RedisDep
from app.models.cluster import Cluster
from app.models.complaint import Complaint
from app.schemas.complaint import (
    ComplaintBatchUpload,
    ComplaintIngest,
    ComplaintResponse,
    IngestResponse,
)
from app.services.complaint_service import get_complaint_by_id, ingest_complaints

router = APIRouter(prefix="/complaints", tags=["complaints"])

_BOROUGH_CENTROIDS: dict[str, tuple[float, float]] = {
    "MANHATTAN":     (40.7831, -73.9712),
    "BROOKLYN":      (40.6782, -73.9442),
    "QUEENS":        (40.7282, -73.7949),
    "BRONX":         (40.8448, -73.8648),
    "STATEN ISLAND": (40.5795, -74.1502),
}


def _derive_latlng(complaint_id: int, region: Optional[str]) -> tuple[float, float] | None:
    if not region:
        return None
    centroid = _BOROUGH_CENTROIDS.get(region.upper().strip())
    if not centroid:
        return None
    rng = random.Random(complaint_id)
    lat_offset = rng.gauss(0, 0.012)
    lng_offset = rng.gauss(0, 0.014)
    return (centroid[0] + lat_offset, centroid[1] + lng_offset)


@router.post(
    "/upload",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest complaints — JSON batch or CSV file",
)
async def upload_complaints(
    request: Request,
    session: DBSessionDep,
    redis: RedisDep,
    celery: CeleryDep,
) -> IngestResponse:
    """Accept complaints via JSON body OR CSV multipart file upload.

    Returns immediately (< 100 ms) — embedding and sentiment are async.
    CSV columns: complaint_text (or text), source, region, product_sku
    """
    content_type = request.headers.get("content-type", "")
    complaints: list[ComplaintIngest] = []

    if "application/json" in content_type:
        try:
            data = await request.json()
            payload = ComplaintBatchUpload.model_validate(data)
            complaints = payload.complaints
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            ) from exc

    elif "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide either a JSON body or a CSV file",
            )
        content = await upload.read()  # type: ignore[union-attr]
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        for row in reader:
            text = row.get("complaint_text") or row.get("text", "")
            if not text.strip():
                continue
            try:
                complaints.append(
                    ComplaintIngest(
                        text=text,
                        source=row.get("source", "crm"),  # type: ignore[arg-type]
                        region=row.get("region") or None,
                        product_sku=row.get("product_sku") or None,
                    )
                )
            except ValidationError:
                continue  # skip malformed rows

    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either a JSON body or a CSV file",
        )

    if not complaints:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No valid complaints in request",
        )

    accepted, queued = await ingest_complaints(complaints, session, redis, celery)

    return IngestResponse(accepted=accepted, queued_for_embedding=queued)


@router.get("/locations", summary="Lat/lng points for all NYC 311 complaints")
async def get_complaint_locations(
    session: DBSessionDep,
    redis: RedisDep,
    limit: int = Query(default=5000, ge=1, le=10000),
    region: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    cache_key = f"complaints:locations:v1:{limit}:{region or 'all'}"
    try:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    stmt = (
        select(
            Complaint.id,
            Complaint.region,
            Complaint.sentiment_label,
            Cluster.label.label("cluster_label"),
        )
        .join(Cluster, Cluster.id == Complaint.cluster_id, isouter=True)
        .where(
            Complaint.source == "nyc_311",
            Complaint.region.is_not(None),
        )
    )
    if region:
        stmt = stmt.where(Complaint.region.ilike(region.strip()))
    stmt = stmt.limit(limit)

    rows = (await session.execute(stmt)).fetchall()
    points = []
    for row in rows:
        latlng = _derive_latlng(row.id, row.region)
        if latlng is None:
            continue
        points.append(
            {
                "id": row.id,
                "lat": round(latlng[0], 6),
                "lng": round(latlng[1], 6),
                "sentiment": row.sentiment_label,
                "cluster_label": row.cluster_label,
                "region": row.region,
            }
        )

    payload: dict[str, Any] = {"points": points, "total": len(points)}
    try:
        await redis.set(cache_key, json.dumps(payload), ex=120)
    except Exception:
        pass
    return payload


@router.get(
    "/{complaint_id}",
    response_model=ComplaintResponse,
    summary="Retrieve a single complaint by ID",
)
async def get_complaint(
    complaint_id: int,
    session: DBSessionDep,
) -> ComplaintResponse:
    """Return the stored (PII-stripped) representation of a complaint."""
    complaint = await get_complaint_by_id(complaint_id, session)
    if complaint is None:
        raise ComplaintNotFoundError(f"Complaint {complaint_id} not found")
    return complaint
