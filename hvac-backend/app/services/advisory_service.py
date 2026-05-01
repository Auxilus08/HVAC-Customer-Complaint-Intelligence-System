"""Claude API call for technician advisory generation.

PII stripping is applied here — BEFORE any Claude API call (second enforcement point).
"""

from __future__ import annotations

from datetime import UTC, datetime

import anthropic
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
representative complaint samples, generate a concise technician advisory in 3-4 bullet points:
- Root cause hypothesis (most probable based on patterns)
- Recommended diagnostic steps for field technician
- Parts likely needed (SKU-level if determinable)
- Escalation criteria (when to escalate to engineering)
Write in clear, actionable language. No jargon. Max 200 words."""


async def generate_advisory(cluster_id: int, session: AsyncSession) -> AdvisoryResponse:
    """Generate a Claude-powered technician advisory for a cluster.

    PII stripping is applied to all complaint samples BEFORE sending to Claude.
    """
    settings = get_settings()

    # Fetch cluster
    result = await session.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if cluster is None:
        raise ClusterNotFoundError(f"Cluster {cluster_id} not found")

    # Fetch up to 10 representative complaint texts
    samples_result = await session.execute(
        select(Complaint.clean_text)
        .where(Complaint.cluster_id == cluster_id)
        .order_by(Complaint.hdbscan_conf.desc().nullslast())
        .limit(10)
    )
    sample_texts: list[str] = [row[0] for row in samples_result.fetchall()]

    if not sample_texts:
        raise AdvisoryServiceError(f"No complaints found for cluster {cluster_id}")

    # ── PII strip BEFORE Claude API call (rule enforced here) ─────────────────
    clean_samples = [strip_pii(t) for t in sample_texts]

    user_message = (
        f"Cluster label: {cluster.label or 'Unlabeled'}\n\n"
        f"Representative complaints ({len(clean_samples)} samples):\n"
        + "\n".join(f"- {t}" for t in clean_samples)
    )

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=400,
            system=_ADVISORY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        if not response.content:
            raise AdvisoryServiceError(
                f"Claude returned empty content for cluster {cluster_id}"
            )
        advisory_text = response.content[0].text  # type: ignore[index]
    except anthropic.APIError as exc:
        logger.error("advisory_claude_api_error", cluster_id=cluster_id, error=str(exc))
        raise AdvisoryServiceError(f"Claude API error: {exc}") from exc

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
