"""NYC 311 HEAT/HOT WATER and air-quality complaints ingest adapter.

Fetches from the NYC Open Data Socrata API and optionally filters to commercial
buildings using a PLUTO BBL CSV (see --pluto-csv flag).

TODO (§F.1): The PLUTO commercial-class BBL snapshot needs to be generated
separately — one-time NYC PLUTO download filtered to BldgClass codes starting
with O, K, H, RB, M. Until that CSV is available the BBL filter is skipped
and all HVAC-relevant 311 complaints are ingested.

Usage:
    python -m scripts.ingest.nyc_311 [--limit N] [--window-days N]
                                      [--pluto-csv PATH] [--mode http]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import structlog

from app.db.session import get_session_factory
from scripts.ingest._common import (
    ChunkedPoster,
    IngestBatchContext,
    IngestStats,
    dedupe_existing,
)

logger = structlog.get_logger(__name__)

ADAPTER_VERSION = "0.1.0"
SOURCE = "nyc_311"
NYC_311_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"

_COMPLAINT_TYPES = (
    "HEAT/HOT WATER",
    "HEATING",
    "AIR QUALITY",
    "INDOOR AIR QUALITY",
    "NONCONST",
)


def _build_soql(limit: int, window_days: int) -> str:
    cutoff = (datetime.now(tz=UTC) - timedelta(days=window_days)).strftime(
        "%Y-%m-%dT%H:%M:%S.000"
    )
    types = ",".join(f"'{t}'" for t in _COMPLAINT_TYPES)
    return (
        "SELECT unique_key, complaint_type, descriptor, resolution_description, "
        f"borough, bbl, created_date "
        f"WHERE complaint_type IN ({types}) "
        f"AND created_date > '{cutoff}' "
        f"ORDER BY created_date DESC "
        f"LIMIT {limit}"
    )


def _load_pluto_csv(path: Path) -> dict[str, str]:
    """Load BBL -> building class mapping from the PLUTO CSV.
    Returns empty dict if file is missing (graceful skip)."""
    if not path.exists():
        logger.warning(
            "pluto_csv_missing",
            path=str(path),
            note="BBL commercial filter skipped; ingest proceeds without it",
        )
        return {}
    pluto: dict[str, str] = {}
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            bbl = row.get("bbl") or row.get("BBL") or ""
            cls = row.get("bldgclass") or row.get("BldgClass") or "UNKNOWN"
            if bbl:
                pluto[bbl.strip()] = cls.strip()
    logger.info("pluto_csv_loaded", record_count=len(pluto))
    return pluto


def _clip(text: str, n: int = 5000) -> str:
    return text[:n]


def _row_to_dict(row: dict, pluto_class: dict[str, str]) -> dict | None:
    text = _clip(
        f"{row.get('complaint_type', '')} — {row.get('descriptor', '')}. "
        f"Resolution: {row.get('resolution_description', '(no resolution recorded)')}"
    )
    if len(text.strip()) < 5:
        return None

    bbl = row.get("bbl", "")
    if pluto_class:
        cls = pluto_class.get(bbl, "UNKNOWN")
        product_sku = f"BLDG-CLASS-{cls}"
    else:
        product_sku = None

    return {
        "external_id": str(row["unique_key"]),
        "text": text,
        "source": SOURCE,
        "region": row.get("borough"),
        "product_sku": product_sku,
        "language": "en",
    }


async def run(
    limit: int = 10000,
    window_days: int = 1825,
    pluto_csv: Path | None = None,
) -> IngestStats:
    pluto_class = _load_pluto_csv(pluto_csv) if pluto_csv else {}

    window_end = datetime.now(tz=UTC)
    window_start = window_end - timedelta(days=window_days)

    async with IngestBatchContext(SOURCE, ADAPTER_VERSION) as batch:
        batch.set_window(window_start, window_end)

        soql = _build_soql(limit, window_days)
        logger.info("nyc_311_fetch_start", limit=limit, window_days=window_days)

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(NYC_311_URL, params={"$query": soql})
            resp.raise_for_status()
            rows = resp.json()

        batch.add_fetched(len(rows))
        logger.info("nyc_311_fetched", count=len(rows))

        external_ids = [r["unique_key"] for r in rows if "unique_key" in r]

        factory = get_session_factory()
        async with factory() as session:
            already_seen = await dedupe_existing(session, SOURCE, external_ids)

        batch.add_skipped_dedupe(len(already_seen))

        complaints: list[dict] = []
        for row in rows:
            uid = row.get("unique_key")
            if not uid or uid in already_seen:
                continue
            record = _row_to_dict(row, pluto_class)
            if record is None:
                batch.add_skipped_validation(1)
                continue
            complaints.append(record)

        logger.info("nyc_311_posting", count=len(complaints))
        poster = ChunkedPoster()
        accepted, queued = await poster.post(complaints)
        batch.add_inserted(accepted)

        logger.info(
            "nyc_311_done",
            inserted=batch.stats.inserted,
            skipped_dedupe=batch.stats.skipped_dedupe,
            skipped_validation=batch.stats.skipped_validation,
        )
        return batch.stats


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NYC 311 HVAC complaints ingest")
    parser.add_argument("--limit", type=int, default=10000, help="Max rows to fetch")
    parser.add_argument(
        "--window-days",
        type=int,
        default=1825,
        dest="window_days",
        help="How far back to fetch (default 1825 = 5 years)",
    )
    parser.add_argument(
        "--pluto-csv",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "data" / "pluto_commercial_bbls.csv",
        dest="pluto_csv",
        help="Path to PLUTO commercial BBL CSV (skipped gracefully if missing)",
    )
    parser.add_argument("--mode", choices=["http", "direct"], default="http")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.mode == "direct":
        raise NotImplementedError("direct mode lands in a follow-up")
    asyncio.run(run(limit=args.limit, window_days=args.window_days, pluto_csv=args.pluto_csv))
