"""Service layer tests — Track A3.

Targets the modules with lowest baseline coverage:
  - cluster.priority_score (formula sanity)
  - cluster_service caching path
  - advisory_service PII gate (Call Site 2)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import Cluster
from app.models.complaint import Complaint


def test_priority_score_formula_basic():
    c = Cluster(
        label="x",
        member_count=100,
        avg_sentiment=-1.0,
        growth_pct_wow=400.0,
        is_emerging=True,
    )
    s = c.priority_score
    # Emerging baseline 1.0, sentiment penalty 1.0, growth boost capped at 1.0
    assert 2.5 <= s <= 4.0


def test_priority_score_handles_none():
    c = Cluster(
        label="x", member_count=10, avg_sentiment=None, growth_pct_wow=None,
        is_emerging=False,
    )
    s = c.priority_score
    assert isinstance(s, float)
    assert s == 0.0


def test_priority_score_emerging_outranks_calm():
    calm = Cluster(label="a", member_count=200, avg_sentiment=-0.1,
                   growth_pct_wow=0.0, is_emerging=False)
    storm = Cluster(label="b", member_count=20, avg_sentiment=-0.9,
                    growth_pct_wow=300.0, is_emerging=True)
    assert storm.priority_score > calm.priority_score


@pytest.mark.asyncio
async def test_cluster_service_returns_emerging_first(test_session: AsyncSession):
    from app.services.cluster_service import list_clusters

    test_session.add_all([
        Cluster(label="calm", member_count=100, avg_sentiment=-0.1,
                is_emerging=False, last_run_id="r"),
        Cluster(label="storm", member_count=20, avg_sentiment=-0.9,
                growth_pct_wow=300.0, is_emerging=True, last_run_id="r"),
    ])
    await test_session.commit()

    result = await list_clusters(test_session)
    labels = [c.label for c in result.clusters]
    assert labels[0] == "storm"


@pytest.mark.asyncio
async def test_advisory_service_strips_pii_before_llm(test_session: AsyncSession):
    """Call Site 2 enforcement: PII must be stripped before the LLM receives anything."""
    from app.services import advisory_service

    cluster = Cluster(label="Compressor", member_count=3, last_run_id="r")
    test_session.add(cluster)
    await test_session.flush()
    test_session.add_all([
        Complaint(
            clean_text="AC not cooling, call me on 9876543210 urgently",
            source="crm", region="Delhi", product_sku="1.5T",
            cluster_id=cluster.id, status="processed",
            sentiment_score=-0.7, sentiment_label="HIGH",
        ),
        Complaint(
            clean_text="Email me at raj.kumar@gmail.com about the unit",
            source="crm", region="Delhi", product_sku="1.5T",
            cluster_id=cluster.id, status="processed",
            sentiment_score=-0.6, sentiment_label="HIGH",
        ),
    ])
    await test_session.commit()

    captured_messages: list[list[dict]] = []

    advisory_text = (
        "## Root Cause\nCompressor wear\n"
        "## Diagnostic Steps\n1. Check oil\n"
        "## Parts Likely Needed\nCompressor\n"
        "## Escalation Criteria\nIf unit fails twice"
    )

    mock_choice = MagicMock()
    mock_choice.message.content = advisory_text
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = (
        lambda model, messages, **kw: captured_messages.append(messages) or mock_response
    )

    with patch("app.services.advisory_service.get_llm_client", return_value=(mock_client, "test-model")):
        result = await advisory_service.generate_advisory(cluster.id, test_session)

    assert result.advisory_text
    assert captured_messages, "LLM should have been called"
    full_prompt = " ".join(
        m["content"] for msgs in captured_messages for m in msgs
    )
    assert "9876543210" not in full_prompt, "PII LEAK: phone reached LLM"
    assert "raj.kumar@gmail.com" not in full_prompt, "PII LEAK: email reached LLM"
    assert "[REDACTED]" in full_prompt, "PII placeholder missing — strip silently failed"
