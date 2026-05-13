"""Standalone Telegram polling runner.

Replaces the Celery beat + worker pair for local/demo use: a single asyncio
loop calls Telegram getUpdates and dispatches each inbound message through
the bot service. Escalation still pushes Complaint rows into the DB; we
also push the embedding + sentiment tasks onto the existing Redis broker
so the docker workers continue to pick them up.

Run from inside the hvac_backend container:
    docker exec -d hvac_backend python scripts/run_telegram_bot.py
or from any environment with the project venv:
    python scripts/run_telegram_bot.py
"""

from __future__ import annotations

import asyncio
import json
import signal
import sys
from pathlib import Path

# Make `app` importable when invoked as `python scripts/...`
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import redis.asyncio as aioredis  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.db.session import get_worker_session_factory  # noqa: E402
from app.services import telegram_bot_service as tbs  # noqa: E402
from app.workers.celery_app import celery_app  # noqa: E402

logger = get_logger(__name__)


async def _process_update(
    update: dict, redis_client: aioredis.Redis, session_factory
) -> None:
    parsed = tbs.extract_inbound(update)
    if not parsed or parsed.get("chat_id") is None:
        return

    has_text = bool(parsed.get("raw_text"))
    has_photo = bool(parsed.get("photo_file_id"))

    # If the message isn't text and isn't a photo (e.g. voice, sticker, video),
    # ask the customer for text — we can't process it yet.
    if not has_text and not has_photo:
        await tbs.send_to_telegram(
            parsed["chat_id"],
            "I can read text and photos of product labels. "
            "Could you send the issue as text, or a photo of the unit's nameplate?",
        )
        return

    try:
        async with session_factory() as session:
            await tbs.handle_inbound_message(
                session,
                chat_id=parsed["chat_id"],
                user_id=parsed.get("user_id"),
                telegram_message_id=parsed.get("telegram_message_id"),
                raw_text=parsed.get("raw_text"),
                customer_name=parsed.get("customer_name"),
                photo_file_id=parsed.get("photo_file_id"),
                photo_caption=parsed.get("photo_caption"),
                celery_app=celery_app,
                redis_client=redis_client,
            )
    except Exception:  # pragma: no cover — keep loop alive
        logger.exception("telegram_handle_message_error", chat_id=parsed.get("chat_id"))


_SINGLETON_LOCK_KEY = "telegram:poller_lock"
# Lock TTL must exceed long-poll timeout so the holder can refresh between polls.
_SINGLETON_LOCK_TTL_SECONDS = 90


async def _acquire_singleton_lock(redis_client: aioredis.Redis, token: str) -> bool:
    """Acquire an exclusive poller lock; returns True on success."""
    return bool(
        await redis_client.set(
            _SINGLETON_LOCK_KEY, token, nx=True, ex=_SINGLETON_LOCK_TTL_SECONDS
        )
    )


async def _refresh_singleton_lock(redis_client: aioredis.Redis, token: str) -> bool:
    """Extend the lock if we still hold it. Returns False if we lost it."""
    current = await redis_client.get(_SINGLETON_LOCK_KEY)
    if current != token:
        return False
    await redis_client.expire(_SINGLETON_LOCK_KEY, _SINGLETON_LOCK_TTL_SECONDS)
    return True


async def _release_singleton_lock(redis_client: aioredis.Redis, token: str) -> None:
    """Release the lock only if we still own it (avoid stealing from a successor)."""
    current = await redis_client.get(_SINGLETON_LOCK_KEY)
    if current == token:
        await redis_client.delete(_SINGLETON_LOCK_KEY)


async def main() -> None:
    import os
    import uuid

    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN is not set — refusing to start.", file=sys.stderr)
        sys.exit(2)

    redis_client = aioredis.from_url(
        settings.REDIS_URL, encoding="utf-8", decode_responses=True
    )
    session_factory = get_worker_session_factory()

    # Singleton guard: two pollers sharing the same getUpdates cursor cause
    # every inbound message to be dispatched twice. Refuse to start if another
    # instance is already polling.
    lock_token = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    if not await _acquire_singleton_lock(redis_client, lock_token):
        holder = await redis_client.get(_SINGLETON_LOCK_KEY)
        print(
            f"Another telegram poller is already running (lock held by {holder}). "
            "Refusing to start — duplicate pollers cause duplicate replies.",
            file=sys.stderr,
        )
        await redis_client.close()
        sys.exit(3)

    stop_event = asyncio.Event()

    def _shutdown(_signum, _frame) -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _shutdown)

    # Resume from last update id stored in Redis (survives restarts)
    offset_key = "telegram:last_update_id"
    raw_offset = await redis_client.get(offset_key)
    offset = (int(raw_offset) + 1) if raw_offset else None

    logger.info(
        "telegram_runner_starting",
        timeout=settings.TELEGRAM_LONG_POLL_TIMEOUT_SECONDS,
        offset=offset,
        lock_token=lock_token,
    )

    try:
        while not stop_event.is_set():
            if not await _refresh_singleton_lock(redis_client, lock_token):
                logger.error("telegram_runner_lost_lock", token=lock_token)
                break

            updates = await tbs.fetch_updates(
                offset=offset,
                timeout_seconds=settings.TELEGRAM_LONG_POLL_TIMEOUT_SECONDS,
            )

            if not updates:
                # Yield to the loop before polling again
                await asyncio.sleep(0.5)
                continue

            # Process all updates concurrently
            await asyncio.gather(
                *(_process_update(u, redis_client, session_factory) for u in updates),
                return_exceptions=True,
            )

            max_id = max(int(u["update_id"]) for u in updates if "update_id" in u)
            offset = max_id + 1
            await redis_client.set(offset_key, str(max_id))
            logger.info(
                "telegram_runner_batch", count=len(updates), last_update_id=max_id
            )
    finally:
        await _release_singleton_lock(redis_client, lock_token)
        await redis_client.close()
        logger.info("telegram_runner_stopped")


if __name__ == "__main__":
    asyncio.run(main())
