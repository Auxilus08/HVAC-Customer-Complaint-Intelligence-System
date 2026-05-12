"""CPSC SaferProducts.gov incident report ingest adapter.

Fetches XML incident reports for Carrier, Bryant, and ICP from the CPSC
SaferProducts REST API and ingests them as complaints.

Usage:
    python -m scripts.ingest.cpsc [--limit N] [--manufacturers Carrier,Bryant,ICP]
                                   [--mode http]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import xml.etree.ElementTree as ET

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
SOURCE = "cpsc"
CPSC_URL = "https://www.saferproducts.gov/RestWebServices/IncidentReport"

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text).strip()


def _clip(text: str, n: int = 5000) -> str:
    return text[:n]


def _safe_text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _parse_reports(xml_bytes: bytes) -> list[dict]:
    """Parse SaferProducts XML into raw record dicts. Returns [] on parse error."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.error("cpsc_xml_parse_error", error=str(exc))
        return []

    reports = []
    for report_el in root.iter("Report"):
        report_number = _safe_text(report_el.find("ReportNumber"))
        if not report_number:
            continue

        incident_desc = _safe_text(report_el.find("IncidentDescription"))
        remedy_desc = _safe_text(report_el.find("RemedyDescription"))

        parts = [_strip_html(incident_desc)]
        if remedy_desc:
            parts.append(_strip_html(remedy_desc))
        text = _clip(" — ".join(p for p in parts if p))

        # State from nested Victim > Location > State
        state = None
        victim_el = report_el.find("Victim")
        if victim_el is not None:
            loc_el = victim_el.find("Location")
            if loc_el is not None:
                state = _safe_text(loc_el.find("State")) or None

        # Product category from Products > Product > ProductCategory
        product_sku = None
        products_el = report_el.find("Products")
        if products_el is not None:
            product_el = products_el.find("Product")
            if product_el is not None:
                category = _safe_text(product_el.find("ProductCategory"))
                if category:
                    product_sku = f"CPSC-{category}"

        reports.append(
            {
                "report_number": report_number,
                "text": text,
                "region": state,
                "product_sku": product_sku,
            }
        )
    return reports


async def _fetch_manufacturer(client: httpx.AsyncClient, manufacturer: str) -> list[dict]:
    """Fetch CPSC reports for one manufacturer. Returns [] on HTTP error."""
    try:
        resp = await client.get(
            CPSC_URL,
            params={"format": "xml", "ManufacturerName": manufacturer},
            timeout=60.0,
        )
        if resp.status_code >= 500:
            logger.error(
                "cpsc_server_error",
                manufacturer=manufacturer,
                status=resp.status_code,
            )
            return []
        resp.raise_for_status()
        records = _parse_reports(resp.content)
        logger.info("cpsc_fetched_manufacturer", manufacturer=manufacturer, count=len(records))
        return records
    except httpx.HTTPError as exc:
        logger.error("cpsc_http_error", manufacturer=manufacturer, error=str(exc))
        return []


async def run(
    limit: int = 1000,
    manufacturers: list[str] | None = None,
) -> IngestStats:
    if manufacturers is None:
        manufacturers = ["Carrier", "Bryant", "ICP"]

    async with IngestBatchContext(SOURCE, ADAPTER_VERSION) as batch:
        all_records: dict[str, dict] = {}  # dedupe by report_number within this run

        async with httpx.AsyncClient() as client:
            for mfr in manufacturers:
                records = await _fetch_manufacturer(client, mfr)
                for rec in records:
                    rn = rec["report_number"]
                    if rn not in all_records:
                        all_records[rn] = rec

        if not all_records:
            # All manufacturers failed — mark batch failed by raising
            raise RuntimeError(
                "CPSC SaferProducts API returned no records for any manufacturer "
                f"({', '.join(manufacturers)}). Network down or schema changed."
            )

        records_list = list(all_records.values())[:limit]
        batch.add_fetched(len(records_list))
        logger.info("cpsc_total_after_dedupe", count=len(records_list))

        # Validation: skip records with < 5 chars of text
        valid_records = []
        for rec in records_list:
            if len(rec["text"].strip()) < 5:
                batch.add_skipped_validation(1)
                continue
            valid_records.append(rec)

        external_ids = [r["report_number"] for r in valid_records]

        factory = get_session_factory()
        async with factory() as session:
            already_seen = await dedupe_existing(session, SOURCE, external_ids)

        batch.add_skipped_dedupe(len(already_seen))

        complaints: list[dict] = []
        for rec in valid_records:
            if rec["report_number"] in already_seen:
                continue
            complaints.append(
                {
                    "external_id": rec["report_number"],
                    "text": rec["text"],
                    "source": SOURCE,
                    "region": rec["region"],
                    "product_sku": rec["product_sku"],
                    "language": "en",
                }
            )

        logger.info("cpsc_posting", count=len(complaints))
        poster = ChunkedPoster()
        accepted, queued = await poster.post(complaints)
        batch.add_inserted(accepted)

        logger.info(
            "cpsc_done",
            inserted=batch.stats.inserted,
            skipped_dedupe=batch.stats.skipped_dedupe,
            skipped_validation=batch.stats.skipped_validation,
        )
        return batch.stats


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CPSC SaferProducts HVAC ingest")
    parser.add_argument("--limit", type=int, default=1000, help="Max records to ingest")
    parser.add_argument(
        "--manufacturers",
        type=lambda s: [m.strip() for m in s.split(",")],
        default="Carrier,Bryant,ICP",
        help="Comma-separated manufacturer names (default: Carrier,Bryant,ICP)",
    )
    parser.add_argument("--mode", choices=["http", "direct"], default="http")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.mode == "direct":
        raise NotImplementedError("direct mode lands in a follow-up")
    asyncio.run(run(limit=args.limit, manufacturers=args.manufacturers))
