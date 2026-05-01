"""Integration tests for GET /api/v1/clusters with filters."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import Cluster


async def _seed_clusters(session: AsyncSession) -> list[int]:
    """Insert test clusters and return their IDs."""
    clusters = [
        Cluster(
            label="Compressor Failure Above 40C",
            member_count=45,
            avg_sentiment=-0.75,
            growth_pct_wow=0.6,
            is_emerging=True,
            last_run_id="run_test_001",
        ),
        Cluster(
            label="Delayed Service Response",
            member_count=20,
            avg_sentiment=-0.3,
            growth_pct_wow=0.1,
            is_emerging=False,
            last_run_id="run_test_001",
        ),
        Cluster(
            label="Positive Feedback Post-Repair",
            member_count=12,
            avg_sentiment=0.65,
            growth_pct_wow=0.0,
            is_emerging=False,
            last_run_id="run_test_001",
        ),
    ]
    for c in clusters:
        session.add(c)
    await session.flush()
    ids = [c.id for c in clusters]
    await session.commit()
    return ids


@pytest.mark.asyncio
class TestClusterAPI:
    async def test_list_clusters_returns_200(
        self, client: AsyncClient, test_session: AsyncSession
    ) -> None:
        await _seed_clusters(test_session)
        resp = await client.get("/api/v1/clusters")
        assert resp.status_code == 200

    async def test_list_clusters_response_shape(
        self, client: AsyncClient, test_session: AsyncSession
    ) -> None:
        await _seed_clusters(test_session)
        resp = await client.get("/api/v1/clusters")
        data = resp.json()
        assert "total" in data
        assert "clusters" in data
        assert isinstance(data["clusters"], list)

    async def test_filter_emerging_only(
        self, client: AsyncClient, test_session: AsyncSession
    ) -> None:
        await _seed_clusters(test_session)
        resp = await client.get("/api/v1/clusters?is_emerging=true")
        assert resp.status_code == 200
        data = resp.json()
        for cluster in data["clusters"]:
            assert cluster["is_emerging"] is True

    async def test_filter_by_run_id(
        self, client: AsyncClient, test_session: AsyncSession
    ) -> None:
        await _seed_clusters(test_session)
        resp = await client.get("/api/v1/clusters?run_id=run_test_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_get_cluster_detail_200(
        self, client: AsyncClient, test_session: AsyncSession
    ) -> None:
        ids = await _seed_clusters(test_session)
        resp = await client.get(f"/api/v1/clusters/{ids[0]}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == ids[0]
        assert "trend" in data
        assert isinstance(data["trend"], list)

    async def test_get_cluster_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/clusters/999999")
        assert resp.status_code == 404

    async def test_pagination_limit(
        self, client: AsyncClient, test_session: AsyncSession
    ) -> None:
        await _seed_clusters(test_session)
        resp = await client.get("/api/v1/clusters?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["clusters"]) <= 1

    async def test_alerts_endpoint(
        self, client: AsyncClient, test_session: AsyncSession
    ) -> None:
        await _seed_clusters(test_session)
        resp = await client.get("/api/v1/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data
        assert "total" in data
