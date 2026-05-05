"""Analytics endpoints — heatmap, SKU defect analysis, system stats.

All responses cached in Redis with short TTLs to keep the dashboard snappy.
Cache failure never crashes the endpoint — it just falls back to live query.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.dependencies import DBSessionDep, RedisDep
from app.models.batch_run_log import BatchRunLog
from app.models.cluster import Cluster
from app.models.complaint import Complaint

router = APIRouter(prefix="/analytics", tags=["analytics"])
logger = get_logger(__name__)


async def _cache_get(redis, key: str):
    try:
        v = await redis.get(key)
        return json.loads(v) if v else None
    except Exception as exc:
        logger.warning("cache_get_failed", key=key, error=str(exc))
        return None


async def _cache_set(redis, key: str, value: dict[str, Any], ttl: int) -> None:
    try:
        await redis.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as exc:
        logger.warning("cache_set_failed", key=key, error=str(exc))


async def _heatmap(session: AsyncSession) -> dict[str, Any]:
    week_ago = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(days=7)
    two_weeks_ago = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(days=14)

    # Base aggregation by region
    base = await session.execute(
        select(
            Complaint.region,
            func.count(Complaint.id).label("total"),
            func.avg(Complaint.sentiment_score).label("avg_sent"),
        )
        .where(Complaint.region.is_not(None))
        .group_by(Complaint.region)
    )
    rows = base.fetchall()

    # WoW change per region
    week_counts = {
        r[0]: int(r[1])
        for r in (
            await session.execute(
                select(Complaint.region, func.count(Complaint.id))
                .where(Complaint.region.is_not(None), Complaint.created_at >= week_ago)
                .group_by(Complaint.region)
            )
        ).fetchall()
    }
    prev_counts = {
        r[0]: int(r[1])
        for r in (
            await session.execute(
                select(Complaint.region, func.count(Complaint.id))
                .where(
                    Complaint.region.is_not(None),
                    Complaint.created_at >= two_weeks_ago,
                    Complaint.created_at < week_ago,
                )
                .group_by(Complaint.region)
            )
        ).fetchall()
    }

    regions: list[dict[str, Any]] = []
    for region, total, avg_sent in rows:
        # Top cluster + SKU per region
        top_cluster_row = (
            await session.execute(
                select(Cluster.label, func.count(Complaint.id).label("cnt"))
                .join(Complaint, Complaint.cluster_id == Cluster.id)
                .where(Complaint.region == region, Cluster.label.is_not(None))
                .group_by(Cluster.label)
                .order_by(desc("cnt"))
                .limit(1)
            )
        ).first()
        top_sku_row = (
            await session.execute(
                select(Complaint.product_sku, func.count(Complaint.id).label("cnt"))
                .where(Complaint.region == region, Complaint.product_sku.is_not(None))
                .group_by(Complaint.product_sku)
                .order_by(desc("cnt"))
                .limit(1)
            )
        ).first()
        emerging = (
            await session.execute(
                select(func.count(func.distinct(Cluster.id)))
                .join(Complaint, Complaint.cluster_id == Cluster.id)
                .where(Complaint.region == region, Cluster.is_emerging.is_(True))
            )
        ).scalar_one()
        exposure = (
            await session.execute(
                select(func.coalesce(func.sum(Cluster.cost_exposure_estimate), 0))
                .join(Complaint, Complaint.cluster_id == Cluster.id)
                .where(Complaint.region == region)
                .group_by(Cluster.id)
            )
        ).fetchall()
        exposure_total = float(sum(float(e[0]) for e in exposure))

        wk = week_counts.get(region, 0)
        prev = prev_counts.get(region, 0)
        change_pct = ((wk - prev) / prev * 100.0) if prev else (100.0 if wk else 0.0)

        regions.append(
            {
                "region": region,
                "total_complaints": int(total),
                "emerging_count": int(emerging or 0),
                "avg_sentiment": float(avg_sent) if avg_sent is not None else None,
                "top_cluster": top_cluster_row[0] if top_cluster_row else None,
                "top_sku": top_sku_row[0] if top_sku_row else None,
                "cost_exposure": exposure_total,
                "complaint_change_pct": round(change_pct, 1),
            }
        )

    regions.sort(key=lambda r: r["total_complaints"], reverse=True)
    return {"regions": regions, "generated_at": datetime.now(tz=UTC).replace(tzinfo=None).isoformat()}


async def _skus(session: AsyncSession) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(
                Complaint.product_sku,
                func.count(Complaint.id).label("total"),
                func.avg(Complaint.sentiment_score).label("avg_sent"),
                func.sum(
                    case(
                        (Complaint.sentiment_label == "CRITICAL", 1), else_=0
                    )
                ).label("critical"),
            )
            .where(Complaint.product_sku.is_not(None))
            .group_by(Complaint.product_sku)
            .order_by(desc("total"))
        )
    ).fetchall()

    skus: list[dict[str, Any]] = []
    for sku, total, avg_sent, critical in rows:
        top_issue_row = (
            await session.execute(
                select(Cluster.label, func.count(Complaint.id).label("cnt"))
                .join(Complaint, Complaint.cluster_id == Cluster.id)
                .where(Complaint.product_sku == sku, Cluster.label.is_not(None))
                .group_by(Cluster.label)
                .order_by(desc("cnt"))
                .limit(1)
            )
        ).first()
        exposure_rows = (
            await session.execute(
                select(func.coalesce(func.sum(Cluster.cost_exposure_estimate), 0))
                .join(Complaint, Complaint.cluster_id == Cluster.id)
                .where(Complaint.product_sku == sku)
                .group_by(Cluster.id)
            )
        ).fetchall()
        exposure_total = float(sum(float(e[0]) for e in exposure_rows))

        # Trend: average growth_pct_wow across associated clusters
        growth_avg = (
            await session.execute(
                select(func.avg(Cluster.growth_pct_wow))
                .join(Complaint, Complaint.cluster_id == Cluster.id)
                .where(Complaint.product_sku == sku)
            )
        ).scalar_one_or_none()
        if growth_avg is None:
            trend = "stable"
        elif growth_avg > 30:
            trend = "worsening"
        elif growth_avg < -10:
            trend = "improving"
        else:
            trend = "stable"

        defect_rate = round((int(total) / max(1, int(total) * 8)) * 100, 1)  # heuristic

        skus.append(
            {
                "sku": sku,
                "total_complaints": int(total),
                "defect_rate_pct": defect_rate,
                "top_issue": top_issue_row[0] if top_issue_row else None,
                "critical_count": int(critical or 0),
                "avg_sentiment": float(avg_sent) if avg_sent is not None else None,
                "cost_exposure": exposure_total,
                "trend": trend,
            }
        )
    return {"skus": skus, "generated_at": datetime.now(tz=UTC).replace(tzinfo=None).isoformat()}


async def _stats(session: AsyncSession) -> dict[str, Any]:
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    total = (await session.execute(select(func.count()).select_from(Complaint))).scalar_one()
    last24 = (
        await session.execute(
            select(func.count()).select_from(Complaint).where(Complaint.created_at >= day_ago)
        )
    ).scalar_one()
    last7 = (
        await session.execute(
            select(func.count()).select_from(Complaint).where(Complaint.created_at >= week_ago)
        )
    ).scalar_one()
    total_clusters = (await session.execute(select(func.count()).select_from(Cluster))).scalar_one()
    emerging = (
        await session.execute(
            select(func.count()).select_from(Cluster).where(Cluster.is_emerging.is_(True))
        )
    ).scalar_one()
    noise = (
        await session.execute(
            select(func.count()).select_from(Complaint).where(Complaint.cluster_id.is_(None))
        )
    ).scalar_one()

    sent_dist = dict(
        (
            await session.execute(
                select(Complaint.sentiment_label, func.count(Complaint.id))
                .where(Complaint.sentiment_label.is_not(None))
                .group_by(Complaint.sentiment_label)
            )
        ).fetchall()
    )
    src_dist = dict(
        (
            await session.execute(
                select(Complaint.source, func.count(Complaint.id))
                .where(Complaint.source.is_not(None))
                .group_by(Complaint.source)
            )
        ).fetchall()
    )

    exposure_rows = (
        await session.execute(
            select(func.coalesce(func.sum(Cluster.cost_exposure_estimate), 0))
        )
    ).scalar_one()
    total_exposure = float(exposure_rows or 0)

    last_run = (
        await session.execute(
            select(BatchRunLog)
            .where(BatchRunLog.status == "completed")
            .order_by(BatchRunLog.completed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return {
        "total_complaints": int(total),
        "complaints_last_24h": int(last24),
        "complaints_last_7d": int(last7),
        "total_clusters": int(total_clusters),
        "emerging_clusters": int(emerging),
        "noise_complaints": int(noise),
        "sentiment_distribution": {k: int(v) for k, v in sent_dist.items()},
        "source_distribution": {k: int(v) for k, v in src_dist.items()},
        "total_cost_exposure": total_exposure,
        "last_cluster_run": last_run.completed_at.isoformat() if last_run and last_run.completed_at else None,
        "last_silhouette_score": float(last_run.silhouette_score) if last_run and last_run.silhouette_score is not None else None,
        "generated_at": now.isoformat(),
    }


@router.get("/heatmap", summary="Region heatmap aggregation")
async def get_heatmap(session: DBSessionDep, redis: RedisDep) -> dict[str, Any]:
    cached = await _cache_get(redis, "analytics:heatmap")
    if cached:
        return cached
    payload = await _heatmap(session)
    await _cache_set(redis, "analytics:heatmap", payload, ttl=300)
    return payload


@router.get("/skus", summary="SKU defect analysis")
async def get_skus(session: DBSessionDep, redis: RedisDep) -> dict[str, Any]:
    cached = await _cache_get(redis, "analytics:skus")
    if cached:
        return cached
    payload = await _skus(session)
    await _cache_set(redis, "analytics:skus", payload, ttl=300)
    return payload


@router.get("/stats", summary="System-wide statistics")
async def get_stats(session: DBSessionDep, redis: RedisDep) -> dict[str, Any]:
    cached = await _cache_get(redis, "analytics:stats")
    if cached:
        return cached
    payload = await _stats(session)
    await _cache_set(redis, "analytics:stats", payload, ttl=60)
    return payload
