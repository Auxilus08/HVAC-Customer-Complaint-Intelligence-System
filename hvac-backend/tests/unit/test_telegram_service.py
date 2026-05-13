"""Unit tests for telegram_bot_service — branching logic with mocked LLM + httpx.

Covers:
  * AI-resolvable path: stores outbound_bot message, status stays open.
  * Human path: marks escalated, creates linked Complaint, sends notice.
  * Awaiting-info path: bot asks follow-up when product can't be matched yet.
  * Agent reply: stores outbound_agent message, flips to agent_active.
  * extract_inbound + keyword pre-filter (pure helpers).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.product import Product
from app.models.support_conversation import SupportConversation
from app.models.support_message import SupportMessage
from app.services import telegram_bot_service as tbs


def _make_llm_response(content: str) -> MagicMock:
    """Build a MagicMock that mimics an openai.ChatCompletion response."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message = MagicMock()
    response.choices[0].message.content = content
    return response


def _seed_llm_responses(*payloads: dict | str) -> MagicMock:
    """Return an OpenAI client mock whose chat.completions.create yields each payload in order."""
    client = MagicMock()
    serialized = [
        p if isinstance(p, str) else json.dumps(p) for p in payloads
    ]
    client.chat.completions.create = MagicMock(
        side_effect=[_make_llm_response(s) for s in serialized]
    )
    return client


async def _seed_product(session: AsyncSession) -> Product:
    product = Product(
        sku="24ANB1",
        family="Infinity",
        model_name="Infinity 19VS Variable-Speed Central AC",
        category="Central Split AC",
        tonnage="2.0",
        seer_rating=19.0,
        common_issues=[
            {"symptom": "no cool air", "resolution_tip": "replace filter"}
        ],
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


@pytest.mark.asyncio
async def test_keyword_prefilter_narrows_large_catalog():
    products = [
        Product(id=i, sku=f"X{i}", model_name=f"Model {i}", family="Infinity")
        for i in range(20)
    ]
    products[3].model_name = "Magic Snowflake Heat Pump"
    snippet = "my magic snowflake unit broke"
    out = tbs._keyword_prefilter(snippet, products, max_candidates=5)
    assert len(out) <= 5
    assert any("Snowflake" in p.model_name for p in out)


def test_extract_inbound_text_message():
    update = {
        "update_id": 42,
        "message": {
            "message_id": 99,
            "chat": {"id": 12345},
            "from": {"id": 6789, "first_name": "Asha", "last_name": "K"},
            "text": "my AC stopped cooling",
        },
    }
    parsed = tbs.extract_inbound(update)
    assert parsed == {
        "chat_id": 12345,
        "user_id": 6789,
        "telegram_message_id": 99,
        "raw_text": "my AC stopped cooling",
        "customer_name": "Asha K",
    }


def test_extract_inbound_non_message_returns_none():
    assert tbs.extract_inbound({"update_id": 1, "callback_query": {}}) is None


def test_extract_inbound_non_text_payload():
    update = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": 5},
            "from": {"id": 6, "username": "x"},
            "photo": [],
        },
    }
    parsed = tbs.extract_inbound(update)
    assert parsed["raw_text"] is None
    assert parsed["chat_id"] == 5


@pytest.mark.asyncio
async def test_handle_inbound_followup_when_no_product_match(
    test_session: AsyncSession, monkeypatch
):
    """When product match returns null, bot asks a follow-up and waits."""
    await _seed_product(test_session)

    fake_client = _seed_llm_responses(
        # match_product → null
        {"sku": None, "confidence": 0.2, "reasoning": "too vague"},
        # ask_followup_question — plain text, not JSON
        "Could you share the model name or family?",
    )
    monkeypatch.setattr(
        tbs, "get_llm_client", lambda: (fake_client, "test-model")
    )
    monkeypatch.setattr(tbs, "send_to_telegram", AsyncMock(return_value=101))

    result = await tbs.handle_inbound_message(
        test_session,
        chat_id=1111,
        user_id=2222,
        telegram_message_id=10,
        raw_text="my AC is broken",
        customer_name="Test Customer",
    )

    assert result["verdict"] == "awaiting_info"
    assert result["escalated"] is False

    conv = (
        await test_session.execute(select(SupportConversation))
    ).scalar_one()
    assert conv.status == "bot_collecting"
    assert conv.matched_product_id is None

    msgs = (
        (await test_session.execute(select(SupportMessage).order_by(SupportMessage.id)))
        .scalars()
        .all()
    )
    # inbound + greeting outbound + followup outbound
    assert [m.direction for m in msgs] == [
        "inbound",
        "outbound_bot",
        "outbound_bot",
    ]
    assert "model name" in msgs[-1].body_redacted.lower()


@pytest.mark.asyncio
async def test_handle_inbound_ai_resolvable_path(
    test_session: AsyncSession, monkeypatch
):
    """High-confidence AI verdict → tip sent, ticket stays open, no complaint row."""
    product = await _seed_product(test_session)

    fake_client = _seed_llm_responses(
        {"sku": product.sku, "confidence": 0.9, "reasoning": "clear match"},
        {
            "verdict": "ai",
            "confidence": 0.85,
            "reasoning": "common issue",
            "suggested_tip": "Replace the filter and reset the breaker.",
        },
    )
    monkeypatch.setattr(
        tbs, "get_llm_client", lambda: (fake_client, "test-model")
    )
    monkeypatch.setattr(tbs, "send_to_telegram", AsyncMock(return_value=202))

    result = await tbs.handle_inbound_message(
        test_session,
        chat_id=3333,
        user_id=4444,
        telegram_message_id=20,
        raw_text="My Infinity 19VS won't cool, indoor unit silent",
        customer_name="Asha",
    )

    assert result["verdict"] == "ai"
    assert result["escalated"] is False
    assert "Replace the filter" in result["reply"]

    conv = (
        await test_session.execute(select(SupportConversation))
    ).scalar_one()
    assert conv.matched_product_id == product.id
    assert conv.status == "bot_collecting"
    assert conv.complaint_id is None

    # No complaint row should be created on AI path
    complaint_count = (
        await test_session.execute(select(Complaint))
    ).scalars().all()
    assert complaint_count == []

    last_msg = (
        (
            await test_session.execute(
                select(SupportMessage).order_by(SupportMessage.id.desc())
            )
        )
        .scalars()
        .first()
    )
    assert last_msg.direction == "outbound_bot"
    assert last_msg.llm_metadata["kind"] == "ai_resolution"


@pytest.mark.asyncio
async def test_handle_inbound_human_path_escalates_and_creates_complaint(
    test_session: AsyncSession, monkeypatch, mock_celery, mock_redis
):
    """Human verdict → status=escalated, complaint row created, escalation notice sent."""
    product = await _seed_product(test_session)

    fake_client = _seed_llm_responses(
        {"sku": product.sku, "confidence": 0.95, "reasoning": "explicit match"},
        {
            "verdict": "human",
            "confidence": 0.9,
            "reasoning": "refrigerant leak suspected",
            "suggested_tip": None,
        },
    )
    monkeypatch.setattr(
        tbs, "get_llm_client", lambda: (fake_client, "test-model")
    )
    monkeypatch.setattr(tbs, "send_to_telegram", AsyncMock(return_value=303))

    result = await tbs.handle_inbound_message(
        test_session,
        chat_id=5555,
        user_id=6666,
        telegram_message_id=30,
        raw_text="There's hissing near my Infinity 19VS indoor coil and a chemical smell",
        customer_name="Priya",
        celery_app=mock_celery,
        redis_client=mock_redis,
    )

    assert result["verdict"] == "human"
    assert result["escalated"] is True

    conv = (
        await test_session.execute(select(SupportConversation))
    ).scalar_one()
    assert conv.status == "escalated"
    assert conv.matched_product_id == product.id
    assert conv.complaint_id is not None
    assert "leak" in (conv.escalation_reason or "").lower()

    complaint = (
        await test_session.execute(
            select(Complaint).where(Complaint.id == conv.complaint_id)
        )
    ).scalar_one()
    assert complaint.source == "telegram"
    assert complaint.product_sku == product.sku
    assert mock_celery.send_task.called


@pytest.mark.asyncio
async def test_send_agent_reply_flips_status_and_persists(
    test_session: AsyncSession, monkeypatch
):
    conv = SupportConversation(
        telegram_chat_id=7777, status="escalated"
    )
    test_session.add(conv)
    await test_session.commit()
    await test_session.refresh(conv)

    monkeypatch.setattr(tbs, "send_to_telegram", AsyncMock(return_value=404))

    msg = await tbs.send_agent_reply(
        test_session,
        conversation_id=conv.id,
        body="Hi, I'm Mark from Carrier — booking a technician now.",
    )
    assert msg.direction == "outbound_agent"
    assert "technician" in msg.body_redacted

    await test_session.refresh(conv)
    assert conv.status == "agent_active"


@pytest.mark.asyncio
async def test_resolve_conversation_marks_closed_and_sends_closing(
    test_session: AsyncSession, monkeypatch
):
    conv = SupportConversation(
        telegram_chat_id=8888, status="agent_active"
    )
    test_session.add(conv)
    await test_session.commit()
    await test_session.refresh(conv)

    monkeypatch.setattr(tbs, "send_to_telegram", AsyncMock(return_value=505))

    closed = await tbs.resolve_conversation(test_session, conversation_id=conv.id)
    assert closed.status == "closed"

    msgs = (
        (await test_session.execute(select(SupportMessage)))
        .scalars()
        .all()
    )
    assert len(msgs) == 1
    assert msgs[0].direction == "outbound_bot"


@pytest.mark.asyncio
async def test_handle_inbound_skips_when_agent_active(
    test_session: AsyncSession, monkeypatch
):
    conv = SupportConversation(
        telegram_chat_id=9999, status="agent_active"
    )
    test_session.add(conv)
    await test_session.commit()

    monkeypatch.setattr(tbs, "send_to_telegram", AsyncMock(return_value=606))
    # If the LLM is touched on this path, raise — we explicitly should not call it.
    def boom():  # pragma: no cover — assertion only fails if reached
        raise AssertionError("LLM must not be invoked when agent is active")

    monkeypatch.setattr(tbs, "get_llm_client", boom)

    result = await tbs.handle_inbound_message(
        test_session,
        chat_id=9999,
        user_id=1,
        telegram_message_id=42,
        raw_text="Hello?",
        customer_name=None,
    )
    assert result["verdict"] == "agent_active"
    assert result["escalated"] is False
    # Inbound stored, no bot reply
    msgs = (
        (await test_session.execute(select(SupportMessage)))
        .scalars()
        .all()
    )
    assert [m.direction for m in msgs] == ["inbound"]
