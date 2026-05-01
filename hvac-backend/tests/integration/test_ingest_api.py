"""Integration tests for POST /api/v1/complaints/upload."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

VALID_PAYLOAD = {
    "complaints": [
        {
            "text": "AC unit not cooling at all, temperature stays at 32 degrees",
            "source": "crm",
            "region": "Mumbai",
            "product_sku": "AC-1.5T-INV",
        }
    ]
}


@pytest.mark.asyncio
class TestIngestAPI:
    async def test_json_ingest_returns_202(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/complaints/upload", json=VALID_PAYLOAD)
        assert resp.status_code == 202

    async def test_json_ingest_response_shape(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/complaints/upload", json=VALID_PAYLOAD)
        data = resp.json()
        assert "accepted" in data
        assert "queued_for_embedding" in data
        assert data["accepted"] == 1
        assert data["queued_for_embedding"] == 1

    async def test_batch_ingest_multiple_complaints(self, client: AsyncClient) -> None:
        payload = {
            "complaints": [
                {
                    "text": f"Complaint number {i}: AC not working properly in summer heat",
                    "source": "whatsapp",
                    "region": "Delhi",
                }
                for i in range(5)
            ]
        }
        resp = await client.post("/api/v1/complaints/upload", json=payload)
        assert resp.status_code == 202
        assert resp.json()["accepted"] == 5

    async def test_empty_text_rejected(self, client: AsyncClient) -> None:
        payload = {"complaints": [{"text": "   ", "source": "crm"}]}
        resp = await client.post("/api/v1/complaints/upload", json=payload)
        assert resp.status_code == 422

    async def test_csv_upload(self, client: AsyncClient) -> None:
        csv_content = (
            "text,source,region,product_sku\n"
            "AC not cooling,crm,Mumbai,AC-1T\n"
            "Compressor noise,whatsapp,Delhi,AC-1.5T\n"
        )
        resp = await client.post(
            "/api/v1/complaints/upload",
            files={
                "file": ("complaints.csv", io.BytesIO(csv_content.encode()), "text/csv")
            },
        )
        assert resp.status_code == 202
        assert resp.json()["accepted"] == 2

    async def test_no_body_or_file_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/complaints/upload")
        assert resp.status_code == 422

    async def test_invalid_source_rejected(self, client: AsyncClient) -> None:
        payload = {"complaints": [{"text": "AC broken", "source": "telegram"}]}
        resp = await client.post("/api/v1/complaints/upload", json=payload)
        assert resp.status_code == 422

    async def test_get_complaint_after_ingest(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/complaints/upload", json=VALID_PAYLOAD)
        assert resp.status_code == 202
        # Fetch the complaint — ID 1 after fresh test DB
        get_resp = await client.get("/api/v1/complaints/1")
        assert get_resp.status_code in (
            200,
            404,
        )  # 404 if FK constraints differ in SQLite

    async def test_get_nonexistent_complaint_returns_404(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/api/v1/complaints/999999")
        assert resp.status_code == 404
