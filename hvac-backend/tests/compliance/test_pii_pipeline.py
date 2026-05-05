"""End-to-end PII pipeline gates — Track C2.

Verifies the two enforcement points:
  Call Site 1 — PII never reaches the database (clean_text column).
  Call Site 2 — PII never reaches Gemini API.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cluster import Cluster
from app.models.complaint import Complaint

pytestmark = pytest.mark.compliance


async def test_pii_stripped_before_db_write(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    body = {
        "complaints": [
            {
                "text": "Call me on 9876543210, AC not cooling",
                "source": "crm",
                "region": "Delhi",
                "product_sku": "1.5T-SPLIT",
            }
        ]
    }
    r = await client.post("/api/v1/complaints/upload", json=body)
    assert r.status_code in (200, 202), r.text

    row = (await test_session.execute(select(Complaint))).scalar_one()
    assert "9876543210" not in row.clean_text, "CRITICAL: phone leaked into DB"
    assert "[REDACTED]" in row.clean_text, "PII placeholder missing — strip silently failed"
    # Signal must survive
    assert "cooling" in row.clean_text.lower()


async def test_pii_stripped_before_gemini_call(test_session: AsyncSession) -> None:
    from app.config import get_settings
    from app.services import advisory_service

    cluster = Cluster(label="Compressor", member_count=2, last_run_id="r")
    test_session.add(cluster)
    await test_session.flush()
    test_session.add_all([
        Complaint(
            clean_text="Call 9876543210 — AC not cooling at all",
            source="crm", region="Delhi", product_sku="1.5T",
            cluster_id=cluster.id, status="processed",
            sentiment_score=-0.7, sentiment_label="HIGH",
        ),
        Complaint(
            clean_text="Email raj@test.com — unit making noise",
            source="crm", region="Delhi", product_sku="1.5T",
            cluster_id=cluster.id, status="processed",
            sentiment_score=-0.6, sentiment_label="HIGH",
        ),
    ])
    await test_session.commit()

    captured: list[str] = []

    class _Resp:
        text = ("## Root Cause\nA\n## Diagnostic Steps\nB\n"
                "## Parts Likely Needed\nC\n## Escalation Criteria\nD")

    class _Model:
        def generate_content(self, msg, generation_config=None):
            captured.append(msg)
            return _Resp()

    settings = get_settings()
    settings.GOOGLE_API_KEY = "test-key"

    with patch.object(advisory_service.genai, "configure", lambda **kw: None), \
         patch.object(advisory_service.genai, "GenerativeModel", return_value=_Model()):
        await advisory_service.generate_advisory(cluster.id, test_session)

    assert captured, "Gemini was never called"
    full = " ".join(captured)
    assert "9876543210" not in full, "CRITICAL: phone reached Gemini API"
    assert "raj@test.com" not in full, "CRITICAL: email reached Gemini API"


async def test_raw_text_encrypted_in_db(test_session: AsyncSession) -> None:
    """raw_text column (when used) is bytes from AES-GCM, not plaintext."""
    from app.core.security import decrypt_raw_text, encrypt_raw_text

    plaintext = "9876543210 raj@test.com — AC not cooling"
    blob = encrypt_raw_text(plaintext)
    assert isinstance(blob, (bytes, bytearray))
    # Encrypted bytes must NOT contain the original UTF-8
    assert plaintext.encode("utf-8") not in bytes(blob)
    # Decryptable round-trip
    assert decrypt_raw_text(blob) == plaintext
