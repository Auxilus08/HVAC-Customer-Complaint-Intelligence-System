"""SLO regression tests — Track D3."""

from __future__ import annotations

import time

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.performance


async def test_ingestion_api_latency(client: AsyncClient) -> None:
    """SLO: POST /complaints/upload returns in <2000ms for 100 rows in tests."""
    rows = [
        {
            "complaint_text": f"complaint number {i}",
            "source": "crm",
            "region": "Delhi",
            "product_sku": "1.5T-SPLIT",
        }
        for i in range(100)
    ]
    cols = list(rows[0].keys())
    csv = ",".join(cols) + "\n" + "\n".join(",".join(f'"{r[c]}"' for c in cols) for r in rows) + "\n"
    body = csv.encode("utf-8")

    t0 = time.perf_counter()
    r = await client.post(
        "/api/v1/complaints/upload",
        files={"file": ("test.csv", body, "text/csv")},
    )
    elapsed = (time.perf_counter() - t0) * 1000
    assert r.status_code == 202
    assert elapsed < 2000, f"ingestion latency {elapsed:.0f}ms > 2000ms"


async def test_cluster_list_latency(client: AsyncClient) -> None:
    """SLO: GET /clusters returns in <500ms (empty DB happy path)."""
    t0 = time.perf_counter()
    r = await client.get("/api/v1/clusters")
    elapsed = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    assert elapsed < 1500, f"cluster list latency {elapsed:.0f}ms > 1500ms"


def test_sentiment_throughput() -> None:
    """SLO: VADER sentiment scoring >= 100 complaints/sec."""
    from pipeline.sentiment import SentimentAnalyzer

    analyzer = SentimentAnalyzer()
    texts = [f"AC complaint number {i}, not working" for i in range(100)]
    t0 = time.perf_counter()
    analyzer.score_batch(texts)
    elapsed = time.perf_counter() - t0
    throughput = len(texts) / max(elapsed, 1e-6)
    assert throughput >= 100, f"sentiment too slow: {throughput:.1f}/s"


def test_embedding_throughput() -> None:
    """SLO: embedder >= 10 complaints/sec on a 50-row warm batch."""
    from pipeline.embedder import Embedder

    embedder = Embedder()
    embedder.encode_single("warmup")  # one-time model load
    texts = [f"AC complaint number {i}" for i in range(50)]
    t0 = time.perf_counter()
    embedder.encode_batch(texts)
    elapsed = time.perf_counter() - t0
    throughput = len(texts) / max(elapsed, 1e-6)
    assert throughput >= 10, f"embedding too slow: {throughput:.1f}/s"
