"""Integration tests for /api/v1/support/* REST endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.support_conversation import SupportConversation
from app.models.support_message import SupportMessage

BASE = "/api/v1/support"


async def _seed_ticket(
    session: AsyncSession, *, status: str = "escalated", with_product: bool = True
) -> tuple[SupportConversation, Product | None]:
    product = None
    if with_product:
        product = Product(
            sku="24ABC6",
            family="Comfort",
            model_name="Comfort 16 Central AC",
            category="Central Split AC",
            tonnage="2.0",
        )
        session.add(product)
        await session.flush()

    conv = SupportConversation(
        telegram_chat_id=42,
        telegram_user_id=43,
        status=status,
        matched_product_id=product.id if product else None,
    )
    session.add(conv)
    await session.flush()

    for body, direction in (
        ("My AC stopped cooling", "inbound"),
        ("Try resetting the breaker", "outbound_bot"),
        ("Still not working", "inbound"),
    ):
        session.add(
            SupportMessage(
                conversation_id=conv.id,
                direction=direction,
                body_redacted=body,
            )
        )
    await session.commit()
    return conv, product


@pytest.mark.asyncio
async def test_list_tickets_empty(client: AsyncClient):
    resp = await client.get(f"{BASE}/tickets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tickets"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_tickets_returns_summary(
    client: AsyncClient, test_session: AsyncSession
):
    conv, product = await _seed_ticket(test_session)

    resp = await client.get(f"{BASE}/tickets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    ticket = data["tickets"][0]
    assert ticket["id"] == conv.id
    assert ticket["status"] == "escalated"
    assert ticket["matched_product"]["sku"] == product.sku
    assert ticket["message_count"] == 3
    assert ticket["last_message_preview"] == "Still not working"
    assert ticket["last_message_direction"] == "inbound"


@pytest.mark.asyncio
async def test_list_tickets_status_filter(
    client: AsyncClient, test_session: AsyncSession
):
    await _seed_ticket(test_session, status="escalated")
    # Seed a second ticket with a different chat_id + closed status
    closed = SupportConversation(telegram_chat_id=99, status="closed")
    test_session.add(closed)
    await test_session.commit()

    resp = await client.get(f"{BASE}/tickets", params={"status": "closed"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["tickets"][0]["status"] == "closed"


@pytest.mark.asyncio
async def test_get_ticket_detail(
    client: AsyncClient, test_session: AsyncSession
):
    conv, product = await _seed_ticket(test_session)

    resp = await client.get(f"{BASE}/tickets/{conv.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == conv.id
    assert data["matched_product"]["sku"] == product.sku
    assert len(data["messages"]) == 3
    assert [m["direction"] for m in data["messages"]] == [
        "inbound",
        "outbound_bot",
        "inbound",
    ]
    # Customer display name is None — we never decrypted/seeded one.
    assert data["customer_display_name"] is None


@pytest.mark.asyncio
async def test_get_ticket_404(client: AsyncClient):
    resp = await client.get(f"{BASE}/tickets/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reply_sends_through_telegram_and_flips_status(
    client: AsyncClient, test_session: AsyncSession, monkeypatch
):
    conv, _ = await _seed_ticket(test_session)

    from app.services import telegram_bot_service

    monkeypatch.setattr(
        telegram_bot_service, "send_to_telegram", AsyncMock(return_value=777)
    )

    resp = await client.post(
        f"{BASE}/tickets/{conv.id}/reply",
        json={"text": "Hi, a technician is on the way today between 3-5 PM."},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["direction"] == "outbound_agent"
    assert "technician" in body["body"]

    # Conversation should now be agent_active
    await test_session.commit()
    refreshed = (
        await test_session.execute(
            select(SupportConversation).where(SupportConversation.id == conv.id)
        )
    ).scalar_one()
    assert refreshed.status == "agent_active"


@pytest.mark.asyncio
async def test_reply_404_on_unknown_ticket(client: AsyncClient):
    resp = await client.post(
        f"{BASE}/tickets/424242/reply", json={"text": "hello?"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reply_validation_rejects_empty(
    client: AsyncClient, test_session: AsyncSession
):
    conv, _ = await _seed_ticket(test_session)
    resp = await client.post(
        f"{BASE}/tickets/{conv.id}/reply", json={"text": "   "}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_resolve_marks_closed(
    client: AsyncClient, test_session: AsyncSession, monkeypatch
):
    conv, _ = await _seed_ticket(test_session, status="agent_active")
    from app.services import telegram_bot_service

    monkeypatch.setattr(
        telegram_bot_service, "send_to_telegram", AsyncMock(return_value=888)
    )

    resp = await client.post(f"{BASE}/tickets/{conv.id}/resolve")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "closed"
    # Last message should be the bot's closing line
    assert data["messages"][-1]["direction"] == "outbound_bot"
