"""PII pattern coverage — Track C1.

Every Indian PII variant must be redacted by app.core.security.strip_pii.
Marker ``compliance`` lets the suite run in isolation and produce a
dedicated audit report.
"""

from __future__ import annotations

import pytest

from app.core.security import strip_pii

pytestmark = pytest.mark.compliance


# ── Indian phone numbers ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [
        "Call me on 9876543210",
        "My number is 98765 43210",
        "Reach me at +91-9876543210",
        "Contact +919876543210",
    ],
)
def test_strips_indian_mobile(raw: str) -> None:
    out = strip_pii(raw)
    assert "9876543210" not in out, f"phone leaked: {out!r}"
    assert "[REDACTED]" in out


def test_preserves_non_phone_numbers() -> None:
    """A spec part-number / capacity / year must not be flagged as a phone."""
    out = strip_pii("My AC model is 15000 BTU unit installed in 2024")
    # Exact string should survive (these aren't 10-digit phone-ish patterns)
    assert "15000" in out and "2024" in out


# ── Aadhaar ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [
        "Aadhaar: 1234 5678 9012",
        "ID: 1234-5678-9012",
        "My aadhaar 123456789012",
    ],
)
def test_strips_aadhaar(raw: str) -> None:
    out = strip_pii(raw)
    for token in ("1234 5678 9012", "1234-5678-9012", "123456789012"):
        assert token not in out
    assert "[REDACTED]" in out


# ── Email ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,leaked",
    [
        ("Email raj.kumar@gmail.com", "raj.kumar@gmail.com"),
        ("Contact me at firstname.lastname@company.co.in", "firstname.lastname@company.co.in"),
    ],
)
def test_strips_email(raw: str, leaked: str) -> None:
    out = strip_pii(raw)
    assert leaked not in out
    assert "[REDACTED]" in out


def test_strips_email_in_sentence() -> None:
    out = strip_pii("Please reply to support@hvac-customer.com for help")
    assert "support@hvac-customer.com" not in out
    assert "Please reply to" in out and "for help" in out


# ── PAN ────────────────────────────────────────────────────────────────────


def test_strips_pan_card() -> None:
    out = strip_pii("My PAN is ABCDE1234F")
    assert "ABCDE1234F" not in out
    assert "[REDACTED]" in out


# ── Combined PII ───────────────────────────────────────────────────────────


def test_strips_multiple_pii_types_in_one_message() -> None:
    text = (
        "Hi, I am Rajesh Kumar, my number is 9876543210, "
        "email is raj@gmail.com and Aadhaar 1234 5678 9012"
    )
    out = strip_pii(text)
    assert "9876543210" not in out
    assert "raj@gmail.com" not in out
    assert "1234 5678 9012" not in out
    assert out.count("[REDACTED]") >= 3


# ── Signal preservation ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,signal",
    [
        ("AC not cooling at all, call me on 9876543210", "cooling"),
        ("Technician raj@gmail.com never showed up", "technician"),
        ("Unit 1.5T-SPLIT making loud noise, Aadhaar 1234 5678 9012", "noise"),
    ],
)
def test_complaint_signal_preserved(raw: str, signal: str) -> None:
    out = strip_pii(raw).lower()
    assert signal in out, f"signal '{signal}' lost after strip: {out!r}"


# ── Idempotency ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    [
        "Call 9876543210 about AC not cooling",
        "Email raj@test.com — compressor noise",
        "Normal complaint with no PII at all",
    ],
)
def test_idempotent_stripping(raw: str) -> None:
    once = strip_pii(raw)
    twice = strip_pii(once)
    assert once == twice, f"strip not idempotent:\n {once!r}\n  != {twice!r}"
