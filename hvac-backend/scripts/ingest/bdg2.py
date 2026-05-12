"""Building Data Genome 2 (BDG2) metadata ingest adapter.

Writes to `commercial_buildings` reference table, not complaints. No PII strip,
no Celery. Pure upsert keyed on building_id.

Source: BDG2 metadata.csv from GitHub. Filtered to commercial primary_use values.

Usage:
    python -m scripts.ingest.bdg2 [--limit N] [--no-filter]
"""

from __future__ import annotations

import argparse
import asyncio
import io

import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import get_session_factory
from app.models.commercial_building import CommercialBuilding
from scripts.ingest._common import IngestBatchContext, IngestStats

logger = structlog.get_logger(__name__)

ADAPTER_VERSION = "0.1.0"
SOURCE = "bdg2"

_BDG2_URLS = [
    "https://media.githubusercontent.com/media/buds-lab/building-data-genome-project-2/master/data/metadata/metadata.csv",
    "https://media.githubusercontent.com/media/buds-lab/building-data-genome-project-2/main/data/metadata/metadata.csv",
    "https://raw.githubusercontent.com/buds-lab/building-data-genome-project-2/master/data/metadata/metadata.csv",
    "https://raw.githubusercontent.com/buds-lab/building-data-genome-project-2/main/data/metadata/metadata.csv",
]

COMMERCIAL_USE = {
    "Office",
    "Education",
    "Healthcare",
    "Public services",
    "Lodging/residential",
    "Food sales and service",
    "Retail",
    "Warehouse/storage",
    "Other",
}

# Metres-squared to square-feet conversion
_SQM_TO_SQFT = 10.7639


async def _download_csv() -> bytes:
    """Try each URL in order; raise RuntimeError if all fail."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        for url in _BDG2_URLS:
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and resp.content:
                    logger.info("bdg2_csv_downloaded", url=url, bytes=len(resp.content))
                    return resp.content
                logger.warning("bdg2_url_failed", url=url, status=resp.status_code)
            except httpx.HTTPError as exc:
                logger.warning("bdg2_url_error", url=url, error=str(exc))

    raise RuntimeError(
        f"BDG2 metadata CSV unavailable at all URLs: {_BDG2_URLS}. "
        "Check https://github.com/buds-lab/building-data-genome-project-2 for the current URL."
    )


def _safe_float(val: str) -> float | None:
    try:
        return float(val) if val else None
    except (ValueError, TypeError):
        return None


def _safe_int(val: str) -> int | None:
    try:
        return int(float(val)) if val else None
    except (ValueError, TypeError):
        return None


def _parse_csv(raw: bytes, limit: int | None, apply_filter: bool) -> list[dict]:
    """Parse BDG2 CSV bytes into upsert-ready dicts. Best-effort column mapping."""
    import csv as _csv

    reader = _csv.DictReader(io.StringIO(raw.decode("utf-8", errors="replace")))
    fieldnames = reader.fieldnames or []
    logger.info("bdg2_csv_columns", columns=list(fieldnames))

    # Best-effort column name normalisation — BDG2 may ship varying casings
    col = {f.lower(): f for f in fieldnames}

    def get(row: dict, *keys: str) -> str:
        for k in keys:
            val = row.get(col.get(k, ""), "")
            if val:
                return val.strip()
        return ""

    records: list[dict] = []
    for row in reader:
        if limit is not None and len(records) >= limit:
            break

        building_id = get(row, "building_id", "id")
        if not building_id:
            continue

        primary_use = get(row, "primaryspaceusage", "primary_space_usage", "primaryuse")

        if apply_filter and primary_use and primary_use not in COMMERCIAL_USE:
            continue

        # sqft: prefer direct sqft, else convert sqm
        sqft_raw = get(row, "sqft")
        sqm_raw = get(row, "sqm")
        sqft: int | None = _safe_int(sqft_raw)
        if sqft is None and sqm_raw:
            sqm = _safe_float(sqm_raw)
            if sqm is not None:
                sqft = int(sqm * _SQM_TO_SQFT)

        # EUI — prefer kbtu/sqft/yr directly; BDG2 often stores as 'eui'
        eui_raw = get(row, "eui", "electricity_eui", "eui_kbtu_per_sqft_yr")
        eui = _safe_float(eui_raw)

        lat_raw = get(row, "lat", "latitude")
        lng_raw = get(row, "lng", "lon", "longitude")

        records.append(
            {
                "building_id": building_id,
                "site_id": get(row, "site_id") or None,
                "primary_use": primary_use or None,
                "sub_primary_use": get(row, "sub_primaryspaceusage", "sub_primary_space_usage") or None,
                "industry": get(row, "industry") or None,
                "sqft": sqft,
                "year_built": _safe_int(get(row, "yearbuilt", "year_built")),
                "floors": _safe_int(get(row, "numberoffloors", "floors")),
                "heating_type": get(row, "heatingtype", "heating_type") or None,
                "state": get(row, "state") or None,
                "country": (get(row, "country") or None),
                "lat": _safe_float(lat_raw),
                "lon": _safe_float(lng_raw),
                "eui_kbtu_per_sqft_yr": eui,
            }
        )

    return records


async def run(limit: int | None = None, apply_filter: bool = True) -> IngestStats:
    async with IngestBatchContext(SOURCE, ADAPTER_VERSION) as batch:
        raw_csv = await _download_csv()
        records = _parse_csv(raw_csv, limit, apply_filter)
        batch.add_fetched(len(records))
        logger.info("bdg2_parsed", count=len(records))

        if not records:
            logger.warning("bdg2_no_records", note="Nothing to upsert")
            return batch.stats

        factory = get_session_factory()
        async with factory() as session:
            stmt = pg_insert(CommercialBuilding).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["building_id"],
                set_={
                    c.key: c
                    for c in stmt.excluded
                    if c.key != "building_id"
                },
            )
            await session.execute(stmt)
            await session.commit()

        batch.add_inserted(len(records))
        logger.info("bdg2_upserted", count=len(records))
        return batch.stats


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BDG2 commercial building metadata ingest"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max rows to process (default: all)",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        dest="no_filter",
        help="Skip the commercial primary_use filter",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(run(limit=args.limit, apply_filter=not args.no_filter))
