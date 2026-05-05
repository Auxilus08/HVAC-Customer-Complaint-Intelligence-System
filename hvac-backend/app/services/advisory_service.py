"""Gemini API call for technician advisory generation.

PII stripping is applied here — BEFORE any Gemini API call (second enforcement point).
"""

from __future__ import annotations

from datetime import UTC, datetime

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import AdvisoryServiceError, ClusterNotFoundError
from app.core.logging import get_logger
from app.core.security import strip_pii
from app.models.cluster import Cluster
from app.models.complaint import Complaint
from app.schemas.cluster import AdvisoryResponse

logger = get_logger(__name__)

_ADVISORY_SYSTEM_PROMPT = """You are an expert HVAC service advisor. Given a cluster label and
representative complaint samples, generate a concise technician advisory in 3-4 sections.
Format the response as Markdown with these section headings (use ## for each):

## Root Cause
The most probable root cause hypothesis based on the complaint patterns.

## Diagnostic Steps
Recommended diagnostic steps for the field technician (numbered list).

## Parts Likely Needed
Parts likely needed, SKU-level if determinable.

## Escalation Criteria
When the technician should escalate to engineering.

Write in clear, actionable language. No jargon. Max 250 words total."""


async def generate_advisory(cluster_id: int, session: AsyncSession) -> AdvisoryResponse:
    """Generate a Gemini-powered technician advisory for a cluster.

    PII stripping is applied to all complaint samples BEFORE sending to Gemini.
    """
    settings = get_settings()

    if not settings.GOOGLE_API_KEY:
        raise AdvisoryServiceError(
            "GOOGLE_API_KEY is not configured. Set it in .env to enable advisory generation."
        )

    result = await session.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if cluster is None:
        raise ClusterNotFoundError(f"Cluster {cluster_id} not found")

    samples_result = await session.execute(
        select(Complaint.clean_text)
        .where(Complaint.cluster_id == cluster_id)
        .order_by(Complaint.hdbscan_conf.desc().nullslast())
        .limit(10)
    )
    sample_texts: list[str] = [row[0] for row in samples_result.fetchall()]

    if not sample_texts:
        raise AdvisoryServiceError(f"No complaints found for cluster {cluster_id}")

    # ── PII strip BEFORE Gemini API call (rule enforced here) ─────────────────
    clean_samples = [strip_pii(t) for t in sample_texts]

    user_message = (
        f"Cluster label: {cluster.label or 'Unlabeled'}\n\n"
        f"Representative complaints ({len(clean_samples)} samples):\n"
        + "\n".join(f"- {t}" for t in clean_samples)
    )

    try:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=_ADVISORY_SYSTEM_PROMPT,
        )
        response = model.generate_content(
            user_message,
            generation_config=genai.GenerationConfig(
                max_output_tokens=600,
                temperature=0.3,
            ),
        )
        advisory_text = (response.text or "").strip()
        if not advisory_text:
            raise AdvisoryServiceError(
                f"Gemini returned empty content for cluster {cluster_id}"
            )
    except AdvisoryServiceError:
        raise
    except Exception as exc:
        logger.error(
            "advisory_gemini_api_error", cluster_id=cluster_id, error=str(exc)
        )
        raise AdvisoryServiceError(f"Gemini API error: {exc}") from exc

    logger.info(
        "advisory_generated",
        cluster_id=cluster_id,
        label=cluster.label,
        sample_count=len(clean_samples),
    )

    return AdvisoryResponse(
        cluster_id=cluster_id,
        label=cluster.label,
        advisory_text=advisory_text,
        generated_at=datetime.now(tz=UTC),
    )
