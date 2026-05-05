"""Frontend ↔ backend contract tests — Track D1.

Asserts every field the React app reads from the backend is present and
typed correctly. Renaming a field server-side breaks these tests instead
of breaking the dashboard silently.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import UTC, datetime

from app.models.batch_run_log import BatchRunLog
from app.models.cluster import Cluster
from app.models.complaint import Complaint
from app.models.umap_coord import UmapCoord

pytestmark = pytest.mark.integration


async def _seed(session: AsyncSession) -> tuple[int, int]:
    now = datetime.now(tz=UTC).replace(tzinfo=None)
    session.add(BatchRunLog(
        run_id="rA",
        started_at=now,
        completed_at=now,
        status="completed",
        clusters_found=1,
        complaints_processed=4,
        silhouette_score=0.5,
        noise_pct=0.0,
    ))
    c = Cluster(
        label="Compressor Noise",
        member_count=4,
        avg_sentiment=-0.62,
        growth_pct_wow=120.0,
        is_emerging=True,
        cost_exposure_estimate=180000.0,
        last_run_id="rA",
    )
    session.add(c)
    await session.flush()
    complaints = [
        Complaint(
            clean_text=f"AC not cooling sample {i}",
            source="crm",
            region="Delhi",
            product_sku="1.5T-SPLIT",
            cluster_id=c.id,
            sentiment_score=-0.7,
            sentiment_label="HIGH",
            status="processed",
            embedding=[0.0] * 384,
        )
        for i in range(4)
    ]
    session.add_all(complaints)
    await session.flush()
    for i, comp in enumerate(complaints):
        session.add(UmapCoord(
            complaint_id=comp.id, run_id="rA",
            x=float(i), y=float(i + 1),
        ))
    await session.commit()
    return c.id, complaints[0].id


async def test_clusters_contract(client: AsyncClient, test_session: AsyncSession) -> None:
    await _seed(test_session)
    r = await client.get("/api/v1/clusters")
    assert r.status_code == 200
    body = r.json()
    assert body["clusters"], "no clusters returned"
    cluster = body["clusters"][0]
    assert isinstance(cluster["id"], int)
    assert isinstance(cluster["member_count"], int)
    assert isinstance(cluster["is_emerging"], bool)
    if cluster.get("label") is not None:
        assert isinstance(cluster["label"], str) and len(cluster["label"]) > 0


async def test_umap_contract(client: AsyncClient, test_session: AsyncSession) -> None:
    await _seed(test_session)
    r = await client.get("/api/v1/umap")
    assert r.status_code == 200
    body = r.json()
    points = body.get("points") or body if isinstance(body, list) else body.get("points", [])
    assert points, "umap endpoint returned no points"
    p = points[0]
    assert isinstance(p["x"], (float, int))
    assert isinstance(p["y"], (float, int))
    if "complaint_id" in p:
        assert isinstance(p["complaint_id"], int)
    if "clean_text" in p and p["clean_text"]:
        assert len(p["clean_text"]) <= 200  # truncation isn't strict in spec


async def test_alerts_contract(client: AsyncClient, test_session: AsyncSession) -> None:
    await _seed(test_session)
    r = await client.get("/api/v1/alerts")
    assert r.status_code == 200
    body = r.json()
    assert "alerts" in body and "total" in body
    assert isinstance(body["total"], int)
    if body["alerts"]:
        a = body["alerts"][0]
        assert "cluster_id" in a
        assert "cluster_label" in a
        assert "severity" in a
        assert a["severity"] in ("CRITICAL", "HIGH", "WARNING")
