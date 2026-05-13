"""Analytics chatbot for the cluster detail page.

The analyst on the dashboard opens a cluster and asks the bot questions like
"what's driving the recent spike?", "which regions are most affected?",
"what should I prioritize?". The bot has the full cluster context (label,
size, sentiment, trend, top SKUs/regions, sample complaints) loaded into
its system prompt and replies with grounded, actionable analysis.

Stateless API — each request from the frontend includes the prior chat
turns, so we don't store anything server-side beyond the cluster context
fetched fresh each time.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ClusterNotFoundError
from app.core.logging import get_logger
from app.core.security import strip_pii
from app.models.cluster import Cluster
from app.models.complaint import Complaint
from app.models.trend_snapshot import TrendSnapshot
from app.services.llm_client import get_llm_client

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are an analytics co-pilot for HVAC support managers.
You are looking at one specific complaint cluster and helping the manager
understand it. The cluster context appears below — use ONLY what's there
to ground your answer. If the manager asks something the data can't answer,
say so plainly rather than guessing.

Guidelines:
- Be concise. 2-4 sentences per turn unless the user asks for depth.
- When citing numbers, use the exact figures from the context.
- When asked "what should I do" or "what's the priority", give a 3-bullet
  prioritized action list, grounded in the cluster's sentiment + trend
  + top SKUs / regions.
- If the trend shows a recent spike (last 3-5 days much higher than earlier
  days), flag it. If sentiment is critical (< -0.6 avg), flag it.
- Never invent SKUs, regions, or complaint quotes.
- Avoid corporate filler. Talk like a senior analyst to another analyst.

Format: plain prose with optional bullet lists. No markdown headers."""


def _format_trend(snapshots: list[TrendSnapshot]) -> str:
    if not snapshots:
        return "(no trend data available)"
    lines = []
    for s in snapshots:
        sent = f"{s.avg_sentiment:.2f}" if s.avg_sentiment is not None else "—"
        lines.append(f"  {s.snapshot_date}: {s.complaint_count} complaints, sentiment={sent}")
    return "\n".join(lines)


async def _build_cluster_context(
    session: AsyncSession, cluster_id: int
) -> dict[str, Any]:
    """Pull everything the LLM needs about the cluster into one dict."""
    cluster = (
        await session.execute(select(Cluster).where(Cluster.id == cluster_id))
    ).scalar_one_or_none()
    if cluster is None:
        raise ClusterNotFoundError(f"Cluster {cluster_id} not found")

    # Trend (last 14 days, oldest → newest for the LLM)
    trend_rows = list(
        (
            await session.execute(
                select(TrendSnapshot)
                .where(TrendSnapshot.cluster_id == cluster_id)
                .order_by(TrendSnapshot.snapshot_date.desc())
                .limit(14)
            )
        )
        .scalars()
        .all()
    )
    trend_rows.reverse()

    # Top SKUs
    sku_rows = (
        await session.execute(
            select(Complaint.product_sku, func.count(Complaint.id).label("cnt"))
            .where(
                Complaint.cluster_id == cluster_id,
                Complaint.product_sku.is_not(None),
            )
            .group_by(Complaint.product_sku)
            .order_by(desc("cnt"))
            .limit(5)
        )
    ).all()
    top_skus = [{"sku": r[0], "count": r[1]} for r in sku_rows]

    # Top regions
    region_rows = (
        await session.execute(
            select(Complaint.region, func.count(Complaint.id).label("cnt"))
            .where(
                Complaint.cluster_id == cluster_id,
                Complaint.region.is_not(None),
            )
            .group_by(Complaint.region)
            .order_by(desc("cnt"))
            .limit(5)
        )
    ).all()
    top_regions = [{"region": r[0], "count": r[1]} for r in region_rows]

    # Sentiment distribution
    sentiment_rows = (
        await session.execute(
            select(Complaint.sentiment_label, func.count(Complaint.id).label("cnt"))
            .where(
                Complaint.cluster_id == cluster_id,
                Complaint.sentiment_label.is_not(None),
            )
            .group_by(Complaint.sentiment_label)
            .order_by(desc("cnt"))
        )
    ).all()
    sentiment_dist = {r[0]: r[1] for r in sentiment_rows}

    # Source distribution
    source_rows = (
        await session.execute(
            select(Complaint.source, func.count(Complaint.id).label("cnt"))
            .where(Complaint.cluster_id == cluster_id, Complaint.source.is_not(None))
            .group_by(Complaint.source)
            .order_by(desc("cnt"))
        )
    ).all()
    source_dist = {r[0]: r[1] for r in source_rows}

    # A handful of representative complaints by best hdbscan confidence —
    # PII-stripped before sending to the LLM (defense in depth).
    sample_rows = (
        await session.execute(
            select(Complaint.clean_text)
            .where(Complaint.cluster_id == cluster_id)
            .order_by(Complaint.hdbscan_conf.desc().nullslast())
            .limit(8)
        )
    ).all()
    samples = [strip_pii(r[0])[:280] for r in sample_rows]

    # Total members (use cluster.member_count when set, otherwise count rows)
    total = cluster.member_count
    if total is None:
        total = (
            await session.execute(
                select(func.count(Complaint.id)).where(
                    Complaint.cluster_id == cluster_id
                )
            )
        ).scalar_one()

    return {
        "id": cluster.id,
        "label": cluster.label,
        "member_count": total,
        "avg_sentiment": cluster.avg_sentiment,
        "is_emerging": cluster.is_emerging,
        "growth_pct_wow": cluster.growth_pct_wow,
        "created_at": cluster.created_at.isoformat() if cluster.created_at else None,
        "trend": trend_rows,
        "top_skus": top_skus,
        "top_regions": top_regions,
        "sentiment_dist": sentiment_dist,
        "source_dist": source_dist,
        "samples": samples,
    }


def _render_context_block(ctx: dict[str, Any]) -> str:
    """Stringify the cluster context for the LLM system prompt."""
    skus_line = (
        ", ".join(f"{s['sku']} ({s['count']})" for s in ctx["top_skus"])
        or "(none)"
    )
    regions_line = (
        ", ".join(f"{r['region']} ({r['count']})" for r in ctx["top_regions"])
        or "(none)"
    )
    sentiment_line = (
        ", ".join(f"{k}={v}" for k, v in ctx["sentiment_dist"].items())
        or "(no labels)"
    )
    source_line = (
        ", ".join(f"{k}={v}" for k, v in ctx["source_dist"].items()) or "(none)"
    )
    samples_block = "\n".join(f"  - {s}" for s in ctx["samples"]) or "  (none)"

    avg_sent = (
        f"{ctx['avg_sentiment']:.3f}" if ctx["avg_sentiment"] is not None else "—"
    )
    growth = (
        f"{ctx['growth_pct_wow']:+.1f}%"
        if ctx["growth_pct_wow"] is not None
        else "—"
    )
    return (
        f"=== CLUSTER #{ctx['id']} CONTEXT ===\n"
        f"Label: {ctx['label'] or '(unlabeled)'}\n"
        f"Members: {ctx['member_count']}\n"
        f"Average sentiment: {avg_sent} (range -1 negative → +1 positive)\n"
        f"Emerging: {ctx['is_emerging']}; week-over-week growth: {growth}\n"
        f"First clustered: {ctx['created_at']}\n"
        f"Sentiment distribution: {sentiment_line}\n"
        f"Source distribution: {source_line}\n"
        f"Top SKUs: {skus_line}\n"
        f"Top regions: {regions_line}\n"
        f"14-day trend (date: count, sentiment):\n{_format_trend(ctx['trend'])}\n"
        f"Representative complaints (PII-redacted):\n{samples_block}\n"
        f"=== END CONTEXT ===\n"
    )


_HISTORY_LIMIT = 20  # cap incoming turns to bound token use


async def chat_with_cluster(
    session: AsyncSession,
    *,
    cluster_id: int,
    history: list[dict[str, str]],
    user_message: str,
) -> dict[str, Any]:
    """Return {reply, cluster_id, generated_at}.

    `history` is a list of {role: 'user'|'assistant', content: str} turns
    from the frontend's session state. The newest user message arrives as
    `user_message`. Cluster context is freshly built each call.
    """
    if not user_message.strip():
        raise ValueError("user_message must not be blank")

    ctx = await _build_cluster_context(session, cluster_id)
    context_block = _render_context_block(ctx)

    client, model = get_llm_client()

    # Build the message list: system (prompt + context) → bounded history → user
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT + "\n\n" + context_block},
    ]
    for turn in history[-_HISTORY_LIMIT:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message.strip()})

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=model,
        messages=messages,
        max_tokens=700,
        temperature=0.3,
    )
    reply = (response.choices[0].message.content or "").strip()

    logger.info(
        "cluster_chat_reply",
        cluster_id=cluster_id,
        history_turns=len(history),
        reply_chars=len(reply),
    )

    return {
        "cluster_id": cluster_id,
        "reply": reply,
        "generated_at": datetime.now(tz=UTC),
        "model": model,
    }
