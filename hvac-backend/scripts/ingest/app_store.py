"""Carrier app store reviews ingest adapter.

Fetches reviews from Google Play and Apple App Store for Carrier-branded
apps. Uses detect_language for language tagging (captures Hinglish from
eService India reviews).

Usage:
    python -m scripts.ingest.app_store [--limit-per-app N] [--mode http]
"""

from __future__ import annotations

import argparse
import asyncio

import structlog

from app.db.session import get_session_factory
from scripts.ingest._common import (
    ChunkedPoster,
    IngestBatchContext,
    IngestStats,
    dedupe_existing,
    detect_language,
)

logger = structlog.get_logger(__name__)

ADAPTER_VERSION = "0.1.0"
SOURCE = "app_store"

APP_TARGETS = [
    # (product_sku, store, app_id, country_codes)
    ("CARRIER-COR-AND",       "play",  "com.carrier.cor",      ["us", "in"]),
    ("CARRIER-COR-IOS",       "apple", "1077005692",           ["us"]),
    ("CARRIER-INFINITY-AND",  "play",  "com.carrier.touch",    ["us"]),
    ("CARRIER-ESERVICE-AND",  "play",  "com.carrier.eservice", ["in"]),
]

_REGION_MAP = {"in": "India", "us": "USA"}


def _clip(text: str, n: int = 5000) -> str:
    return text[:n]


def _fetch_play_reviews(app_id: str, country: str, limit: int) -> list[dict]:
    """Fetch Google Play reviews. Returns [] on any error (e.g., unknown app_id)."""
    try:
        from google_play_scraper import reviews as gp_reviews
        result, _ = gp_reviews(
            app_id,
            count=limit,
            lang="en",
            country=country,
        )
        return result
    except Exception as exc:
        logger.warning(
            "play_reviews_fetch_error",
            app_id=app_id,
            country=country,
            error=str(exc),
        )
        return []


def _fetch_apple_reviews(app_id: str, country: str, limit: int) -> list[dict]:
    """Fetch Apple App Store reviews. Returns [] on any error."""
    try:
        from app_store_scraper import AppStore
        app = AppStore(country=country, app_id=app_id)
        app.review(how_many=limit)
        return app.reviews
    except Exception as exc:
        logger.warning(
            "apple_reviews_fetch_error",
            app_id=app_id,
            country=country,
            error=str(exc),
        )
        return []


def _play_review_to_dict(
    r: dict, product_sku: str, country: str
) -> dict | None:
    text = _clip(r.get("content") or "")
    if len(text.strip()) < 5:
        return None
    lang = detect_language(text)
    return {
        "external_id": f"play:{r['reviewId']}",
        "text": text,
        "source": SOURCE,
        "region": _REGION_MAP.get(country),
        "product_sku": product_sku,
        "language": lang,
    }


def _apple_review_to_dict(
    r: dict, product_sku: str, country: str
) -> dict | None:
    text = _clip(r.get("review") or r.get("content") or "")
    if len(text.strip()) < 5:
        return None
    lang = detect_language(text)
    return {
        "external_id": f"apple:{r['id']}",
        "text": text,
        "source": SOURCE,
        "region": _REGION_MAP.get(country),
        "product_sku": product_sku,
        "language": lang,
    }


async def run(limit_per_app: int = 500) -> IngestStats:
    async with IngestBatchContext(SOURCE, ADAPTER_VERSION) as batch:
        # Collect all reviews across all targets; dedupe by external_id within run
        seen_in_run: set[str] = set()
        all_records: list[dict] = []

        for product_sku, store, app_id, countries in APP_TARGETS:
            for country in countries:
                logger.info(
                    "app_store_fetching",
                    store=store,
                    app_id=app_id,
                    country=country,
                    limit=limit_per_app,
                )
                if store == "play":
                    raw_reviews = await asyncio.to_thread(
                        _fetch_play_reviews, app_id, country, limit_per_app
                    )
                    for r in raw_reviews:
                        rec = _play_review_to_dict(r, product_sku, country)
                        if rec is None:
                            batch.add_skipped_validation(1)
                            continue
                        if rec["external_id"] not in seen_in_run:
                            seen_in_run.add(rec["external_id"])
                            all_records.append(rec)
                elif store == "apple":
                    raw_reviews = await asyncio.to_thread(
                        _fetch_apple_reviews, app_id, country, limit_per_app
                    )
                    for r in raw_reviews:
                        rec = _apple_review_to_dict(r, product_sku, country)
                        if rec is None:
                            batch.add_skipped_validation(1)
                            continue
                        if rec["external_id"] not in seen_in_run:
                            seen_in_run.add(rec["external_id"])
                            all_records.append(rec)
                else:
                    logger.warning("unknown_store", store=store, app_id=app_id)

        batch.add_fetched(len(all_records))
        logger.info("app_store_total_collected", count=len(all_records))

        external_ids = [r["external_id"] for r in all_records]

        factory = get_session_factory()
        async with factory() as session:
            already_seen = await dedupe_existing(session, SOURCE, external_ids)

        batch.add_skipped_dedupe(len(already_seen))

        complaints = [r for r in all_records if r["external_id"] not in already_seen]

        logger.info("app_store_posting", count=len(complaints))
        poster = ChunkedPoster()
        accepted, queued = await poster.post(complaints)
        batch.add_inserted(accepted)

        logger.info(
            "app_store_done",
            inserted=batch.stats.inserted,
            skipped_dedupe=batch.stats.skipped_dedupe,
            skipped_validation=batch.stats.skipped_validation,
        )
        return batch.stats


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carrier app store reviews ingest")
    parser.add_argument(
        "--limit-per-app",
        type=int,
        default=500,
        dest="limit_per_app",
        help="Max reviews to fetch per app+country combination",
    )
    parser.add_argument("--mode", choices=["http", "direct"], default="http")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.mode == "direct":
        raise NotImplementedError("direct mode lands in a follow-up")
    asyncio.run(run(limit_per_app=args.limit_per_app))
