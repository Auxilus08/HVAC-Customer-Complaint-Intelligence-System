"""Complaint ingestion and retrieval endpoints."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from app.core.exceptions import ComplaintNotFoundError
from app.dependencies import CeleryDep, DBSessionDep, RedisDep
from app.schemas.complaint import (
    ComplaintBatchUpload,
    ComplaintIngest,
    ComplaintResponse,
    IngestResponse,
)
from app.services.complaint_service import get_complaint_by_id, ingest_complaints

router = APIRouter(prefix="/complaints", tags=["complaints"])


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
