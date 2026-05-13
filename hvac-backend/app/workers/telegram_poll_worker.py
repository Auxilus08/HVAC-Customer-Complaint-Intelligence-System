"""Celery worker: poll the Telegram Bot API for inbound messages.

Two tasks:
  * ``poll_updates``: scheduled by Celery Beat every TELEGRAM_POLL_INTERVAL_SECONDS;
    calls Telegram's getUpdates (long-poll, blocking up to
    TELEGRAM_LONG_POLL_TIMEOUT_SECONDS) and dispatches each update to the
    handler task.
  * ``handle_message``: processes one update — opens a DB session and calls
    :func:`telegram_bot_service.handle_inbound_message`.

A `last_update_id` cursor is persisted in Redis so restarts don't replay
already-processed messages.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import redis
from celery import Task

from app.config import get_settings
from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

_REDIS_OFFSET_KEY = "telegram:last_update_id"


class TelegramTask(Task):
    """Base task with a lazy sync Redis client + DB session factory."""

    abstract = True
    _redis: redis.Redis | None = None

    @property
    def redis_client(self) -> redis.Redis:
        if self._redis is None:
            settings = get_settings()
            self._redis = redis.Redis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
        return self._redis


@celery_app.task(
    bind=True,
    base=TelegramTask,
    name="app.workers.telegram_poll_worker.poll_updates",
    queue="telegram",
)
def poll_updates(self: TelegramTask) -> dict[str, Any]:
    """One iteration of long-poll → dispatch loop. Scheduled by Beat."""
    settings = get_settings()
    if not settings.TELEGRAM_ENABLED:
        return {"status": "disabled"}
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("telegram_poll_skipped_no_token")
        return {"status": "no_token"}

    offset_raw = self.redis_client.get(_REDIS_OFFSET_KEY)
    offset = int(offset_raw) + 1 if offset_raw else None

    from app.services.telegram_bot_service import fetch_updates

    updates = asyncio.run(
        fetch_updates(
            offset=offset,
            timeout_seconds=settings.TELEGRAM_LONG_POLL_TIMEOUT_SECONDS,
        )
    )

    dispatched = 0
    max_update_id = None
    for update in updates:
        update_id = update.get("update_id")
        if update_id is None:
            continue
        max_update_id = (
            update_id if max_update_id is None else max(max_update_id, update_id)
        )
        celery_app.send_task(
            "app.workers.telegram_poll_worker.handle_message",
            args=[json.dumps(update)],
            queue="telegram",
        )
        dispatched += 1

    if max_update_id is not None:
        self.redis_client.set(_REDIS_OFFSET_KEY, str(max_update_id))

    logger.info(
        "telegram_poll_iteration",
        received=len(updates),
        dispatched=dispatched,
        last_update_id=max_update_id,
    )
    return {
        "status": "ok",
        "received": len(updates),
        "dispatched": dispatched,
        "last_update_id": max_update_id,
    }


@celery_app.task(
    bind=True,
    base=TelegramTask,
    name="app.workers.telegram_poll_worker.handle_message",
    queue="telegram",
    max_retries=3,
    default_retry_delay=15,
)
def handle_message(self: TelegramTask, update_json: str) -> dict[str, Any]:
    """Process a single Telegram update."""
    try:
        update = json.loads(update_json)
    except json.JSONDecodeError as exc:
        logger.error("telegram_handle_message_bad_json", error=str(exc))
        return {"status": "bad_json"}

    from app.services.telegram_bot_service import extract_inbound

    parsed = extract_inbound(update)
    if not parsed or parsed.get("chat_id") is None:
        return {"status": "skipped", "reason": "not_a_message"}

    if not parsed.get("raw_text"):
        # Non-text payload (photo, voice, sticker). Reply with a polite ask.
        from app.services.telegram_bot_service import send_to_telegram

        asyncio.run(
            send_to_telegram(
                parsed["chat_id"],
                "I can only read text messages right now — could you describe "
                "the issue in text?",
            )
        )
        return {"status": "non_text"}

    try:
        result = asyncio.run(_handle_message_async(parsed))
        return result
    except Exception as exc:  # pragma: no cover — logged + retried
        logger.error(
            "telegram_handle_message_error",
            error=str(exc),
            chat_id=parsed.get("chat_id"),
        )
        raise self.retry(exc=exc, countdown=15 * (2**self.request.retries)) from exc


async def _handle_message_async(parsed: dict[str, Any]) -> dict[str, Any]:
    """Async body of handle_message — opens a session and delegates."""
    import redis.asyncio as aioredis

    from app.db.session import get_worker_session_factory
    from app.services.telegram_bot_service import handle_inbound_message

    settings = get_settings()
    factory = get_worker_session_factory()

    redis_client = aioredis.from_url(
        settings.REDIS_URL, encoding="utf-8", decode_responses=True
    )
    try:
        async with factory() as session:
            result = await handle_inbound_message(
                session,
                chat_id=parsed["chat_id"],
                user_id=parsed.get("user_id"),
                telegram_message_id=parsed.get("telegram_message_id"),
                raw_text=parsed["raw_text"],
                customer_name=parsed.get("customer_name"),
                celery_app=celery_app,
                redis_client=redis_client,
            )
        return result
    finally:
        await redis_client.close()
