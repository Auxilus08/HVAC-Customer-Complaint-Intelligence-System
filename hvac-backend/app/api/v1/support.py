"""HTTP endpoints for the human-agent Support Inbox.

All responses use the PII-redacted message body (``body_redacted``) — raw
text lives only in the encrypted blob and is never exposed via API.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select

from app.core.logging import get_logger
from app.dependencies import DBSessionDep
from app.models.support_message import SupportMessage
from app.schemas.support import (
    AgentReplyIn,
    ProductSummary,
    SupportMessageOut,
    SupportTicketDetail,
    SupportTicketSummary,
    TicketListResponse,
)
from app.services import telegram_bot_service

logger = get_logger(__name__)

router = APIRouter(prefix="/support", tags=["support"])


def _product_to_summary(product) -> ProductSummary | None:
    if product is None:
        return None
    return ProductSummary.model_validate(product)


@router.get(
    "/tickets",
    response_model=TicketListResponse,
    summary="List support tickets (Telegram conversations) for the agent inbox",
)
async def list_tickets(
    session: DBSessionDep,
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description=(
            "Filter by conversation status: bot_collecting | bot_resolved | "
            "escalated | agent_active | closed"
        ),
    ),
    limit: int = Query(default=100, ge=1, le=500),
) -> TicketListResponse:
    rows = await telegram_bot_service.list_tickets(
        session, status_filter=status_filter, limit=limit
    )
    tickets = [
        SupportTicketSummary(
            id=r["id"],
            status=r["status"],
            matched_product=_product_to_summary(r["matched_product"]),
            last_message_preview=r["last_message_preview"],
            last_message_direction=r["last_message_direction"],
            message_count=r["message_count"],
            created_at=r["created_at"],
            last_message_at=r["last_message_at"],
        )
        for r in rows
    ]
    return TicketListResponse(tickets=tickets, total=len(tickets))


@router.get(
    "/tickets/{ticket_id}",
    response_model=SupportTicketDetail,
    summary="Full conversation thread + matched product for a ticket",
)
async def get_ticket(
    ticket_id: int, session: DBSessionDep
) -> SupportTicketDetail:
    detail = await telegram_bot_service.get_ticket_detail(session, ticket_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    conversation = detail["conversation"]
    return SupportTicketDetail(
        id=conversation.id,
        status=conversation.status,
        matched_product=_product_to_summary(detail["matched_product"]),
        escalation_reason=conversation.escalation_reason,
        complaint_id=conversation.complaint_id,
        customer_display_name=detail["customer_display_name"],
        gathered_info=conversation.gathered_info,
        created_at=conversation.created_at,
        last_message_at=conversation.last_message_at,
        messages=[SupportMessageOut.from_orm_row(m) for m in detail["messages"]],
    )


@router.post(
    "/tickets/{ticket_id}/reply",
    response_model=SupportMessageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Send a human-agent reply through the Telegram bot",
)
async def reply_to_ticket(
    ticket_id: int, payload: AgentReplyIn, session: DBSessionDep
) -> SupportMessageOut:
    try:
        message = await telegram_bot_service.send_agent_reply(
            session, conversation_id=ticket_id, body=payload.text
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    logger.info(
        "agent_reply_sent",
        ticket_id=ticket_id,
        message_id=message.id,
    )
    return SupportMessageOut.from_orm_row(message)


@router.get(
    "/messages/{message_id}/image",
    summary="Download the photo a customer attached to a support message",
    responses={
        200: {"content": {"image/*": {}}},
        404: {"description": "Message not found or has no image"},
    },
)
async def get_message_image(
    message_id: int, session: DBSessionDep
) -> Response:
    msg = (
        await session.execute(
            select(SupportMessage).where(SupportMessage.id == message_id)
        )
    ).scalar_one_or_none()
    if msg is None or not msg.image_encrypted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message has no image",
        )
    decoded = telegram_bot_service.decrypt_inbound_image(msg)
    if decoded is None:  # pragma: no cover — guarded by has-image check above
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not available"
        )
    image_bytes, mime = decoded
    return Response(
        content=image_bytes,
        media_type=mime,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.post(
    "/tickets/{ticket_id}/resolve",
    response_model=SupportTicketDetail,
    summary="Mark a ticket as resolved and send the customer a closing message",
)
async def resolve_ticket(
    ticket_id: int, session: DBSessionDep
) -> SupportTicketDetail:
    try:
        await telegram_bot_service.resolve_conversation(
            session, conversation_id=ticket_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    detail = await telegram_bot_service.get_ticket_detail(session, ticket_id)
    if detail is None:  # pragma: no cover — just-resolved row must exist
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found after resolve",
        )
    conversation = detail["conversation"]
    return SupportTicketDetail(
        id=conversation.id,
        status=conversation.status,
        matched_product=_product_to_summary(detail["matched_product"]),
        escalation_reason=conversation.escalation_reason,
        complaint_id=conversation.complaint_id,
        customer_display_name=detail["customer_display_name"],
        gathered_info=conversation.gathered_info,
        created_at=conversation.created_at,
        last_message_at=conversation.last_message_at,
        messages=[SupportMessageOut.from_orm_row(m) for m in detail["messages"]],
    )
