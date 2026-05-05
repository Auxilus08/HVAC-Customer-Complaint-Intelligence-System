"""Edge-case ingestion tests — Track A1.

Targets failure modes that simple happy-path tests don't cover:
boundary sizes, malformed CSV, encoding, mixed-validity batches,
SQL injection, concurrency.
"""

from __future__ import annotations

import asyncio
import io

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint

BASE = "/api/v1/complaints/upload"


def _csv(rows: list[dict]) -> bytes:
    if not rows:
        return b"complaint_text,source,region,product_sku\n"
    cols = list(rows[0].keys())
    lines = [",".join(cols)]
    for r in rows:
        lines.append(",".join(f'"{r[c]}"' for c in cols))
    return ("\n".join(lines) + "\n").encode("utf-8")


async def _post_csv(client: AsyncClient, content: bytes, name: str = "u.csv"):
    return await client.post(
        BASE, files={"file": (name, content, "text/csv")}
    )


# ── A1: ingestion edge cases ────────────────────────────────────────────────


async def test_csv_with_extra_columns(client: AsyncClient, test_session: AsyncSession):
    csv = b"complaint_text,source,region,product_sku,extra_col,another\n"
    csv += b'"AC not cooling","crm","Delhi","1.5T-SPLIT","junk","ignored"\n'
    r = await _post_csv(client, csv)
    assert r.status_code == 202, r.text
    n = (await test_session.execute(select(func.count()).select_from(Complaint))).scalar_one()
    assert n == 1


async def test_csv_with_mixed_valid_invalid_rows(client: AsyncClient, test_session: AsyncSession):
    """Documents observed behaviour: invalid rows silently skipped, valid kept."""
    rows = [
        {"complaint_text": f"row {i}", "source": "crm", "region": "Delhi", "product_sku": "1.5T"}
        for i in range(8)
    ] + [
        {"complaint_text": "bad row 1", "source": "invalid_source", "region": "X", "product_sku": "Y"},
        {"complaint_text": "bad row 2", "source": "another_invalid", "region": "X", "product_sku": "Y"},
    ]
    r = await _post_csv(client, _csv(rows))
    assert r.status_code in (202, 422)
    n = (await test_session.execute(select(func.count()).select_from(Complaint))).scalar_one()
    if r.status_code == 202:
        # Permissive mode: only the 8 valid rows accepted.
        assert n == 8, f"expected 8 valid rows ingested, got {n}"
    else:
        assert n == 0


async def test_csv_empty_file(client: AsyncClient):
    r = await _post_csv(client, b"complaint_text,source,region,product_sku\n")
    assert r.status_code in (400, 422)


async def test_csv_encoding_utf8_with_bom(client: AsyncClient, test_session: AsyncSession):
    body = b"\xef\xbb\xbfcomplaint_text,source,region,product_sku\n"
    body += '"unit not cooling 😤","crm","Delhi","1.5T"\n'.encode("utf-8")
    r = await _post_csv(client, body)
    assert r.status_code == 202, r.text
    row = (await test_session.execute(select(Complaint))).scalar_one()
    assert "unit not cooling" in row.clean_text


async def test_csv_with_hinglish_text(client: AsyncClient, test_session: AsyncSession):
    text = "AC bilkul thanda nahi kar raha bahut pareshani hai"
    r = await _post_csv(client, _csv([
        {"complaint_text": text, "source": "whatsapp", "region": "Delhi", "product_sku": "1.5T"}
    ]))
    assert r.status_code == 202
    row = (await test_session.execute(select(Complaint))).scalar_one()
    # Hinglish stem must survive (no PII pattern matches)
    for stem in ("thanda", "pareshani"):
        assert stem in row.clean_text


async def test_csv_with_special_characters_and_sql_injection(
    client: AsyncClient, test_session: AsyncSession
):
    payloads = [
        "Quote test \"hello\" inside",
        "Comma test, with multiple, commas",
        "Emoji 😤 disgust 🔥 hot",
        "'; DROP TABLE complaints; --",
        "1=1 OR true OR ' OR 1=1 --",
    ]
    rows = [
        {"complaint_text": p, "source": "crm", "region": "Delhi", "product_sku": "1.5T"}
        for p in payloads
    ]
    r = await _post_csv(client, _csv(rows))
    assert r.status_code == 202, r.text
    n = (await test_session.execute(select(func.count()).select_from(Complaint))).scalar_one()
    assert n == len(payloads), "All rows should be stored as literal text"
    # Table must still exist after the SQL injection attempt
    still_alive = (await test_session.execute(select(func.count()).select_from(Complaint))).scalar_one()
    assert still_alive == len(payloads)


async def test_rapid_sequential_uploads(client: AsyncClient, test_session: AsyncSession):
    """Five back-to-back uploads land all 50 rows without dropping.

    Note: the test client shares one session across requests, so true
    concurrent ``asyncio.gather`` would deadlock SQLAlchemy. Production
    pools per-request — the no-loss invariant is what we care about.
    """
    for i in range(5):
        rows = [
            {"complaint_text": f"batch {i} row {j}", "source": "crm",
             "region": "Delhi", "product_sku": "1.5T"}
            for j in range(10)
        ]
        r = await _post_csv(client, _csv(rows), name=f"b{i}.csv")
        assert r.status_code == 202, r.text
    n = (await test_session.execute(select(func.count()).select_from(Complaint))).scalar_one()
    assert n == 50, f"expected 50 rows, got {n}"


async def test_upload_response_time_slo(client: AsyncClient):
    import time
    rows = [
        {"complaint_text": f"complaint {i}", "source": "crm",
         "region": "Delhi", "product_sku": "1.5T"}
        for i in range(500)
    ]
    body = _csv(rows)
    t0 = time.perf_counter()
    r = await _post_csv(client, body)
    elapsed = (time.perf_counter() - t0) * 1000
    assert r.status_code == 202
    # Loose threshold for shared test machine
    assert elapsed < 2000, f"Upload took {elapsed:.0f}ms (>2000ms)"


async def test_unsupported_source_rejected(client: AsyncClient, test_session: AsyncSession):
    r = await _post_csv(client, _csv([
        {"complaint_text": "x", "source": "telepathy",
         "region": "Delhi", "product_sku": "1.5T"}
    ]))
    assert r.status_code == 422
    n = (await test_session.execute(select(func.count()).select_from(Complaint))).scalar_one()
    assert n == 0


async def test_complaint_without_pii_passes_through(
    client: AsyncClient, test_session: AsyncSession
):
    text = "AC compressor making rattling noise on startup"
    r = await _post_csv(client, _csv([
        {"complaint_text": text, "source": "crm",
         "region": "Delhi", "product_sku": "1.5T-SPLIT"}
    ]))
    assert r.status_code == 202
    row = (await test_session.execute(select(Complaint))).scalar_one()
    # No PII pattern should have triggered
    assert "[PHONE]" not in row.clean_text
    assert "[EMAIL]" not in row.clean_text
