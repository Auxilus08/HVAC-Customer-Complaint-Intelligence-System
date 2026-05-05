"""API response shape contracts — Track A2.

These tests lock the JSON shape of every endpoint the frontend consumes.
Renaming or removing a field breaks these tests immediately, before the
frontend hits the bad payload at runtime.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import Cluster
from app.models.complaint import Complaint


async def _seed(session: AsyncSession) -> int:
    """Insert one cluster + a couple of complaints so endpoints have data."""
    c = Cluster(
        label="Compressor Noise",
        member_count=10,
        avg_sentiment=-0.62,
        growth_pct_wow=120.0,
        is_emerging=True,
        cost_exposure_estimate=180000.0,
        last_run_id="run_test",
    )
    session.add(c)
    await session.flush()
    session.add_all([
        Complaint(
            clean_text=f"AC not cooling {i}",
            source="crm",
            region="Delhi",
            product_sku="1.5T-SPLIT",
            cluster_id=c.id,
            sentiment_score=-0.7,
            sentiment_label="HIGH",
            status="processed",
        )
        for i in range(3)
    ])
    await session.commit()
    return c.id


async def test_clusters_response_shape(client: AsyncClient, test_session: AsyncSession):
    await _seed(test_session)
    r = await client.get("/api/v1/clusters")
    assert r.status_code == 200
    body = r.json()
    assert "clusters" in body and "total" in body
    cluster = body["clusters"][0]
    # cost_exposure_estimate is Numeric(12,2) → JSON-serialized as string.
    required = {
        "id": int,
        "label": (str, type(None)),
        "member_count": (int, type(None)),
        "avg_sentiment": (float, type(None)),
        "growth_pct_wow": (float, type(None)),
        "is_emerging": bool,
        "cost_exposure_estimate": (float, str, type(None)),
    }
    for field, t in required.items():
        assert field in cluster, f"missing field {field}"
        v = cluster[field]
        if isinstance(t, tuple):
            assert isinstance(v, t), f"{field} has type {type(v).__name__}"
        else:
            assert isinstance(v, t), f"{field} has type {type(v).__name__}"


async def test_alerts_response_shape(client: AsyncClient, test_session: AsyncSession):
    await _seed(test_session)
    r = await client.get("/api/v1/alerts")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "alerts" in body and "total" in body
    assert isinstance(body["total"], int)
    if body["alerts"]:
        a = body["alerts"][0]
        for field in ("cluster_id", "cluster_label", "severity"):
            assert field in a
        assert a["severity"] in ("CRITICAL", "HIGH", "WARNING")


async def test_health_response_shape(client: AsyncClient):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded", "down")
    assert "version" in body
    assert "checks" in body
    for ch in ("database", "redis", "ml_pipeline", "gemini_api"):
        assert ch in body["checks"]
        assert "status" in body["checks"][ch]


async def test_error_response_shape(client: AsyncClient):
    r = await client.get("/api/v1/clusters/99999")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body or "detail" in body
    # Must NOT leak Python tracebacks
    serialized = str(body)
    assert "Traceback" not in serialized
    assert "  File " not in serialized


async def test_stats_response_shape(client: AsyncClient, test_session: AsyncSession):
    await _seed(test_session)
    r = await client.get("/api/v1/analytics/stats")
    assert r.status_code == 200
    body = r.json()
    for field in (
        "total_complaints",
        "complaints_last_24h",
        "total_clusters",
        "emerging_clusters",
        "sentiment_distribution",
        "source_distribution",
        "total_cost_exposure",
        "generated_at",
    ):
        assert field in body, f"stats missing {field}"
    assert isinstance(body["sentiment_distribution"], dict)
    assert isinstance(body["source_distribution"], dict)


async def test_search_response_shape(client: AsyncClient, test_session: AsyncSession):
    await _seed(test_session)
    r = await client.get("/api/v1/complaints/search?q=cooling&limit=5")
    assert r.status_code == 200
    body = r.json()
    for field in ("complaints", "total", "limit", "offset", "has_more"):
        assert field in body
    assert isinstance(body["total"], int)
    assert isinstance(body["has_more"], bool)
