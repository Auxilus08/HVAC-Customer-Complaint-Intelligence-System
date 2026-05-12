"""Analytics endpoints — heatmap, SKU defect analysis, system stats.

All responses cached in Redis with short TTLs to keep the dashboard snappy.
Cache failure never crashes the endpoint — it just falls back to live query.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.dependencies import DBSessionDep, RedisDep
from app.models.batch_run_log import BatchRunLog
from app.models.cluster import Cluster
from app.models.commercial_building import CommercialBuilding
from app.models.complaint import Complaint
from app.models.ingest_batch import IngestBatch

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


async def _sources(session: AsyncSession) -> dict[str, Any]:
    # Latest ingest_batch per source
    latest_subq = (
        select(
            IngestBatch.source,
            IngestBatch.completed_at,
            IngestBatch.status,
            IngestBatch.source_window_start,
            IngestBatch.source_window_end,
            IngestBatch.records_inserted,
        )
        .distinct(IngestBatch.source)
        .order_by(IngestBatch.source, IngestBatch.started_at.desc())
        .subquery("latest_batch")
    )

    counts_subq = (
        select(
            Complaint.source.label("source"),
            func.count(Complaint.id).label("total_records"),
        )
        .where(Complaint.source.is_not(None))
        .group_by(Complaint.source)
        .subquery("counts")
    )

    rows = (
        await session.execute(
            select(
                counts_subq.c.source,
                counts_subq.c.total_records,
                latest_subq.c.completed_at,
                latest_subq.c.status,
                latest_subq.c.source_window_start,
                latest_subq.c.source_window_end,
                latest_subq.c.records_inserted,
            )
            .select_from(counts_subq)
            .outerjoin(latest_subq, counts_subq.c.source == latest_subq.c.source)
            .order_by(desc(counts_subq.c.total_records))
        )
    ).fetchall()

    sources: list[dict[str, Any]] = []
    for row in rows:
        sources.append(
            {
                "source": row[0],
                "total_records": int(row[1]),
                "last_refresh": row[2].isoformat() if row[2] else None,
                "last_status": row[3],
                "source_window_start": row[4].isoformat() if row[4] else None,
                "source_window_end": row[5].isoformat() if row[5] else None,
                "records_inserted_last_run": int(row[6]) if row[6] is not None else None,
            }
        )

    return {"sources": sources, "generated_at": datetime.now(tz=UTC).replace(tzinfo=None).isoformat()}


async def _buildings(session: AsyncSession) -> dict[str, Any]:
    total = (
        await session.execute(select(func.count()).select_from(CommercialBuilding))
    ).scalar_one()

    by_use_rows = (
        await session.execute(
            select(
                CommercialBuilding.primary_use,
                func.count(CommercialBuilding.building_id).label("cnt"),
                func.avg(CommercialBuilding.eui_kbtu_per_sqft_yr).label("avg_eui"),
                func.avg(CommercialBuilding.sqft).label("avg_sqft"),
            )
            .where(CommercialBuilding.primary_use.is_not(None))
            .group_by(CommercialBuilding.primary_use)
            .order_by(desc("cnt"))
            .limit(10)
        )
    ).fetchall()

    by_state_rows = (
        await session.execute(
            select(
                CommercialBuilding.state,
                func.count(CommercialBuilding.building_id).label("cnt"),
            )
            .where(CommercialBuilding.state.is_not(None))
            .group_by(CommercialBuilding.state)
            .order_by(desc("cnt"))
            .limit(10)
        )
    ).fetchall()

    return {
        "by_primary_use": [
            {
                "primary_use": row[0],
                "count": int(row[1]),
                "avg_eui": round(float(row[2]), 2) if row[2] is not None else None,
                "avg_sqft": round(float(row[3]), 1) if row[3] is not None else None,
            }
            for row in by_use_rows
        ],
        "by_state": [
            {"state": row[0], "count": int(row[1])}
            for row in by_state_rows
        ],
        "total_buildings": int(total),
        "generated_at": datetime.now(tz=UTC).replace(tzinfo=None).isoformat(),
    }


@router.get("/sources", summary="Data source provenance and last-refresh status")
async def get_sources(session: DBSessionDep, redis: RedisDep) -> dict[str, Any]:
    cached = await _cache_get(redis, "analytics:sources")
    if cached:
        return cached
    payload = await _sources(session)
    await _cache_set(redis, "analytics:sources", payload, ttl=60)
    return payload


@router.get("/buildings", summary="Commercial building reference analytics")
async def get_buildings(session: DBSessionDep, redis: RedisDep) -> dict[str, Any]:
    cached = await _cache_get(redis, "analytics:buildings")
    if cached:
        return cached
    payload = await _buildings(session)
    await _cache_set(redis, "analytics:buildings", payload, ttl=60)
    return payload


_BOROUGHS = ["MANHATTAN", "BROOKLYN", "QUEENS", "BRONX", "STATEN ISLAND"]


async def _region_heatmap(session: AsyncSession) -> dict[str, Any]:
    # Top 10 clusters by member_count with non-null labels
    top_clusters_rows = (
        await session.execute(
            select(Cluster.id, Cluster.label, Cluster.member_count)
            .where(Cluster.label.is_not(None), Cluster.member_count.is_not(None))
            .order_by(desc(Cluster.member_count))
            .limit(10)
        )
    ).fetchall()

    if not top_clusters_rows:
        return {"regions": _BOROUGHS, "themes": [], "matrix": [], "max_value": 0}

    cluster_ids = [row[0] for row in top_clusters_rows]

    # Count complaints per (cluster_id, normalized region)
    crosstab_rows = (
        await session.execute(
            select(
                Complaint.cluster_id,
                func.upper(func.trim(Complaint.region)).label("region_norm"),
                func.count(Complaint.id).label("cnt"),
            )
            .where(
                Complaint.cluster_id.in_(cluster_ids),
                func.upper(func.trim(Complaint.region)).in_(_BOROUGHS),
            )
            .group_by(Complaint.cluster_id, func.upper(func.trim(Complaint.region)))
        )
    ).fetchall()

    # Build lookup: (cluster_id, region) -> count
    cell_map: dict[tuple, int] = {}
    for cluster_id, region_norm, cnt in crosstab_rows:
        cell_map[(cluster_id, region_norm)] = int(cnt)

    themes = [
        {"label": row[1], "total": int(row[2])}
        for row in top_clusters_rows
    ]

    matrix: list[list[int]] = []
    for row in top_clusters_rows:
        cluster_id = row[0]
        matrix.append([cell_map.get((cluster_id, borough), 0) for borough in _BOROUGHS])

    max_value = max((cell for row in matrix for cell in row), default=0)

    return {
        "regions": _BOROUGHS,
        "themes": themes,
        "matrix": matrix,
        "max_value": max_value,
    }


@router.get("/region_heatmap", summary="Borough × issue theme heatmap")
async def get_region_heatmap(session: DBSessionDep, redis: RedisDep) -> dict[str, Any]:
    cached = await _cache_get(redis, "analytics:region_heatmap:v1")
    if cached:
        return cached
    payload = await _region_heatmap(session)
    await _cache_set(redis, "analytics:region_heatmap:v1", payload, ttl=60)
    return payload


# ---------------------------------------------------------------------------
# Mock geographic data — Carrier global footprint (no DB query)
# Tuples: (key, name, count, top_city, lat, lng)
# ---------------------------------------------------------------------------

_WORLD_DATA = [
    ("USA", "United States",       18420, "New York, NY",          40.7128,  -74.0060),
    ("IND", "India",               11250, "Mumbai",                19.0760,   72.8777),
    ("CHN", "China",                8920, "Shanghai",              31.2304,  121.4737),
    ("BRA", "Brazil",               3210, "São Paulo",            -23.5505,  -46.6333),
    ("MEX", "Mexico",               2840, "Mexico City",           19.4326,  -99.1332),
    ("CAN", "Canada",               2410, "Toronto",               43.6532,  -79.3832),
    ("SAU", "Saudi Arabia",         2280, "Riyadh",                24.7136,   46.6753),
    ("ARE", "United Arab Emirates", 2150, "Dubai",                 25.2048,   55.2708),
    ("GBR", "United Kingdom",       1980, "London",                51.5074,   -0.1278),
    ("DEU", "Germany",              1740, "Berlin",                52.5200,   13.4050),
    ("FRA", "France",               1620, "Paris",                 48.8566,    2.3522),
    ("ESP", "Spain",                1480, "Madrid",                40.4168,   -3.7038),
    ("ITA", "Italy",                1390, "Milan",                 45.4642,    9.1900),
    ("JPN", "Japan",                1280, "Tokyo",                 35.6762,  139.6503),
    ("KOR", "South Korea",          1150, "Seoul",                 37.5665,  126.9780),
    ("AUS", "Australia",            1040, "Sydney",               -33.8688,  151.2093),
    ("SGP", "Singapore",             920, "Singapore",              1.3521,  103.8198),
    ("MYS", "Malaysia",              810, "Kuala Lumpur",           3.1390,  101.6869),
    ("THA", "Thailand",              760, "Bangkok",               13.7563,  100.5018),
    ("IDN", "Indonesia",             690, "Jakarta",               -6.2088,  106.8456),
    ("VNM", "Vietnam",               610, "Ho Chi Minh City",      10.7626,  106.6602),
    ("PHL", "Philippines",           540, "Manila",                14.5995,  120.9842),
    ("ZAF", "South Africa",          490, "Johannesburg",         -26.2041,   28.0473),
    ("EGY", "Egypt",                 450, "Cairo",                 30.0444,   31.2357),
    ("TUR", "Turkey",                420, "Istanbul",              41.0082,   28.9784),
    ("POL", "Poland",                380, "Warsaw",                52.2297,   21.0122),
    ("NLD", "Netherlands",           340, "Amsterdam",             52.3676,    4.9041),
    ("CHE", "Switzerland",           290, "Zurich",                47.3769,    8.5417),
    ("SWE", "Sweden",                240, "Stockholm",             59.3293,   18.0686),
    ("NOR", "Norway",                210, "Oslo",                  59.9139,   10.7522),
    ("ARG", "Argentina",             580, "Buenos Aires",         -34.6037,  -58.3816),
    ("COL", "Colombia",              410, "Bogotá",                 4.7110,  -74.0721),
    ("CHL", "Chile",                 340, "Santiago",             -33.4489,  -70.6693),
    ("PER", "Peru",                  260, "Lima",                 -12.0464,  -77.0428),
    ("QAT", "Qatar",                 720, "Doha",                  25.2854,   51.5310),
    ("KWT", "Kuwait",                580, "Kuwait City",           29.3759,   47.9774),
    ("OMN", "Oman",                  340, "Muscat",                23.5859,   58.4059),
    ("ISR", "Israel",                480, "Tel Aviv",              32.0853,   34.7818),
    ("KAZ", "Kazakhstan",            180, "Almaty",                43.2389,   76.8897),
    ("NGA", "Nigeria",               160, "Lagos",                  6.5244,    3.3792),
]

_USA_DATA = [
    ("FL", "Florida",              3850, "Miami",              25.7617,  -80.1918),
    ("TX", "Texas",                3420, "Houston",            29.7604,  -95.3698),
    ("CA", "California",           3180, "Los Angeles",        34.0522, -118.2437),
    ("NY", "New York",             5210, "New York, NY",       40.7128,  -74.0060),
    ("PA", "Pennsylvania",          980, "Philadelphia",       39.9526,  -75.1652),
    ("IL", "Illinois",              940, "Chicago",            41.8781,  -87.6298),
    ("OH", "Ohio",                  820, "Columbus",           39.9612,  -82.9988),
    ("GA", "Georgia",               790, "Atlanta",            33.7490,  -84.3880),
    ("NC", "North Carolina",        740, "Charlotte",          35.2271,  -80.8431),
    ("MI", "Michigan",              680, "Detroit",            42.3314,  -83.0458),
    ("NJ", "New Jersey",            630, "Newark",             40.7357,  -74.1724),
    ("VA", "Virginia",              590, "Virginia Beach",     36.8529,  -75.9780),
    ("WA", "Washington",            540, "Seattle",            47.6062, -122.3321),
    ("AZ", "Arizona",               920, "Phoenix",            33.4484, -112.0740),
    ("MA", "Massachusetts",         480, "Boston",             42.3601,  -71.0589),
    ("TN", "Tennessee",             460, "Nashville",          36.1627,  -86.7816),
    ("IN", "Indiana",               420, "Indianapolis",       39.7684,  -86.1581),
    ("MO", "Missouri",              390, "Kansas City",        39.0997,  -94.5786),
    ("MD", "Maryland",              370, "Baltimore",          39.2904,  -76.6122),
    ("WI", "Wisconsin",             320, "Milwaukee",          43.0389,  -87.9065),
    ("CO", "Colorado",              310, "Denver",             39.7392, -104.9903),
    ("MN", "Minnesota",             280, "Minneapolis",        44.9778,  -93.2650),
    ("SC", "South Carolina",        350, "Charleston",         32.7765,  -79.9311),
    ("AL", "Alabama",               320, "Birmingham",         33.5186,  -86.8104),
    ("LA", "Louisiana",             370, "New Orleans",        29.9511,  -90.0715),
    ("KY", "Kentucky",              260, "Louisville",         38.2527,  -85.7585),
    ("OR", "Oregon",                240, "Portland",           45.5051, -122.6750),
    ("OK", "Oklahoma",              290, "Oklahoma City",      35.4676,  -97.5164),
    ("CT", "Connecticut",           310, "Hartford",           41.7658,  -72.6851),
    ("UT", "Utah",                  220, "Salt Lake City",     40.7608, -111.8910),
    ("NV", "Nevada",                410, "Las Vegas",          36.1699, -115.1398),
    ("AR", "Arkansas",              220, "Little Rock",        34.7465,  -92.2896),
    ("MS", "Mississippi",           230, "Jackson",            32.2988,  -90.1848),
    ("KS", "Kansas",                200, "Wichita",            37.6872,  -97.3301),
    ("IA", "Iowa",                  180, "Des Moines",         41.5868,  -93.6250),
    ("NM", "New Mexico",            220, "Albuquerque",        35.0844, -106.6504),
    ("HI", "Hawaii",                290, "Honolulu",           21.3069, -157.8583),
    ("DC", "District of Columbia",  320, "Washington, DC",     38.9072,  -77.0369),
    ("WV", "West Virginia",         130, "Charleston",         38.3498,  -81.6326),
    ("NE", "Nebraska",              150, "Omaha",              41.2565,  -95.9345),
    ("ID", "Idaho",                 140, "Boise",              43.6150, -116.2023),
    ("ME", "Maine",                 110, "Portland",           43.6591,  -70.2568),
    ("NH", "New Hampshire",         120, "Manchester",         42.9956,  -71.4548),
    ("RI", "Rhode Island",          150, "Providence",         41.8240,  -71.4128),
    ("MT", "Montana",                90, "Billings",           45.7833, -108.5007),
    ("DE", "Delaware",              160, "Wilmington",         39.7447,  -75.5484),
    ("SD", "South Dakota",           80, "Sioux Falls",        43.5446,  -96.7311),
    ("ND", "North Dakota",           70, "Fargo",              46.8772,  -96.7898),
    ("AK", "Alaska",                 80, "Anchorage",          61.2181, -149.9003),
    ("WY", "Wyoming",                60, "Cheyenne",           41.1400, -104.8202),
    ("VT", "Vermont",                90, "Burlington",         44.4759,  -73.2121),
]

_INDIA_DATA = [
    ("MH", "Maharashtra",      2840, "Mumbai",               19.0760,  72.8777),
    ("KA", "Karnataka",        1980, "Bengaluru",            12.9716,  77.5946),
    ("TN", "Tamil Nadu",       1720, "Chennai",              13.0827,  80.2707),
    ("DL", "Delhi",            1580, "New Delhi",            28.6139,  77.2090),
    ("GJ", "Gujarat",           980, "Ahmedabad",            23.0225,  72.5714),
    ("TG", "Telangana",         920, "Hyderabad",            17.3850,  78.4867),
    ("UP", "Uttar Pradesh",     780, "Lucknow",              26.8467,  80.9462),
    ("WB", "West Bengal",       640, "Kolkata",              22.5726,  88.3639),
    ("RJ", "Rajasthan",         420, "Jaipur",               26.9124,  75.7873),
    ("HR", "Haryana",           380, "Gurugram",             28.4595,  77.0266),
    ("PB", "Punjab",            260, "Chandigarh",           30.7333,  76.7794),
    ("AP", "Andhra Pradesh",    320, "Visakhapatnam",        17.6868,  83.2185),
    ("KL", "Kerala",            280, "Kochi",                 9.9312,  76.2673),
    ("MP", "Madhya Pradesh",    240, "Indore",               22.7196,  75.8577),
    ("BR", "Bihar",             180, "Patna",                25.5941,  85.1376),
    ("OR", "Odisha",            150, "Bhubaneswar",          20.2961,  85.8245),
    ("JK", "Jammu and Kashmir",  90, "Srinagar",             34.0837,  74.7973),
    ("AS", "Assam",              80, "Guwahati",             26.1445,  91.7362),
    ("UK", "Uttarakhand",        70, "Dehradun",             30.3165,  78.0322),
    ("HP", "Himachal Pradesh",   60, "Shimla",               31.1048,  77.1734),
    ("GA", "Goa",                90, "Panaji",               15.4909,  73.8278),
    ("CG", "Chhattisgarh",       60, "Raipur",               21.2514,  81.6296),
    ("JH", "Jharkhand",          50, "Ranchi",               23.3441,  85.3096),
    ("TR", "Tripura",            20, "Agartala",             23.8315,  91.2868),
    ("CH", "Chandigarh",         70, "Chandigarh",           30.7333,  76.7794),
    ("PY", "Puducherry",         40, "Puducherry",           11.9416,  79.8083),
    ("LD", "Lakshadweep",        10, "Kavaratti",            10.5667,  72.6417),
    ("AN", "Andaman and Nicobar", 15, "Port Blair",          11.6234,  92.7265),
]


def _build_geo_payload(level: str, rows: list[tuple]) -> dict[str, Any]:
    regions = [
        {"key": key, "name": name, "count": count, "top_city": city, "lat": lat, "lng": lng}
        for key, name, count, city, lat, lng in rows
    ]
    regions.sort(key=lambda r: r["count"], reverse=True)
    max_count = max((r["count"] for r in regions), default=0)
    total = sum(r["count"] for r in regions)
    return {
        "level": level,
        "regions": regions,
        "max_count": max_count,
        "total": total,
        "_note": "mock data generated for Carrier global footprint; NYC complaints are real NYC 311 data",
    }


@router.get("/geo", summary="Geographic complaint volume by country, US state, or India state")
async def get_geo(
    redis: RedisDep,
    level: str = Query(..., description="'world', 'usa', or 'india'"),
) -> dict[str, Any]:
    if level not in ("world", "usa", "india"):
        raise HTTPException(
            status_code=400,
            detail=f"level={level!r} is not supported. Use 'world', 'usa', or 'india'.",
        )
    cache_key = f"analytics:geo:{level}"
    cached = await _cache_get(redis, cache_key)
    if cached:
        return cached
    if level == "world":
        rows = _WORLD_DATA
    elif level == "usa":
        rows = _USA_DATA
    else:
        rows = _INDIA_DATA
    payload = _build_geo_payload(level, rows)
    await _cache_set(redis, cache_key, payload, ttl=300)
    return payload


@router.get("/cities", summary="Top cities globally for city-marker layer")
async def get_cities(redis: RedisDep) -> dict[str, Any]:
    cache_key = "analytics:cities"
    cached = await _cache_get(redis, cache_key)
    if cached:
        return cached

    # Aggregate top city per country + per US state + per India state, dedupe by lat/lng
    seen: set[tuple[float, float]] = set()
    cities: list[dict[str, Any]] = []

    for rows, source in ((_WORLD_DATA, "world"), (_USA_DATA, "usa"), (_INDIA_DATA, "india")):
        for key, name, count, city_name, lat, lng in rows:
            coord = (round(lat, 2), round(lng, 2))
            if coord in seen:
                continue
            seen.add(coord)
            cities.append({
                "name": city_name,
                "country": key if source == "world" else name,
                "count": count,
                "lat": lat,
                "lng": lng,
            })

    cities.sort(key=lambda c: c["count"], reverse=True)
    max_count = max((c["count"] for c in cities), default=0)
    payload = {"cities": cities, "total": len(cities), "max_count": max_count}
    await _cache_set(redis, cache_key, payload, ttl=300)
    return payload
