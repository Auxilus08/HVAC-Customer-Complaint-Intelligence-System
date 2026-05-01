"""Unit tests for PII stripping — phone, email, Aadhaar, PAN patterns."""

from __future__ import annotations

from app.core.security import strip_pii, strip_pii_regex


class TestPhoneRedaction:
    def test_indian_mobile_10digit(self) -> None:
        result = strip_pii_regex("Call me on 9876543210 for help")
        assert "9876543210" not in result
        assert "[REDACTED]" in result

    def test_indian_mobile_with_country_code(self) -> None:
        result = strip_pii_regex("Contact: +91 98765 43210")
        assert "98765" not in result

    def test_non_phone_number_preserved(self) -> None:
        result = strip_pii_regex("Model number 12345 failed")
        assert "12345" in result  # 5-digit, not a phone

    def test_multiple_phones_in_text(self) -> None:
        text = "Primary: 9876543210, Secondary: 8765432109"
        result = strip_pii_regex(text)
        assert "9876543210" not in result
        assert "8765432109" not in result


class TestEmailRedaction:
    def test_standard_email(self) -> None:
        result = strip_pii_regex("Send invoice to user@example.com")
        assert "user@example.com" not in result
        assert "[REDACTED]" in result

    def test_email_with_dots_and_plus(self) -> None:
        result = strip_pii_regex("Reach me at first.last+tag@domain.co.in")
        assert "first.last" not in result

    def test_no_false_positive_on_filename(self) -> None:
        result = strip_pii_regex("Error in config.py at line 42")
        assert "config.py" in result  # not an email


class TestAadhaarRedaction:
    def test_aadhaar_12digit(self) -> None:
        result = strip_pii_regex("My Aadhaar is 1234 5678 9012")
        assert "1234" not in result or "5678" not in result

    def test_aadhaar_no_spaces(self) -> None:
        result = strip_pii_regex("Aadhar: 123456789012")
        assert "123456789012" not in result

    def test_aadhaar_with_dashes(self) -> None:
        result = strip_pii_regex("ID: 1234-5678-9012")
        assert "1234-5678-9012" not in result


class TestPANRedaction:
    def test_valid_pan(self) -> None:
        result = strip_pii_regex("PAN: ABCDE1234F submitted")
        assert "ABCDE1234F" not in result

    def test_lowercase_pan_not_matched(self) -> None:
        # PAN regex requires uppercase — lowercase should not be redacted
        result = strip_pii_regex("abcde1234f")
        assert "abcde1234f" in result


class TestFullPipeline:
    def test_complaint_with_mixed_pii(self) -> None:
        complaint = (
            "My AC is broken. Call Rahul at 9999988888 or rahul@gmail.com. "
            "His Aadhaar is 1234 5678 9011."
        )
        result = strip_pii(complaint)
        assert "9999988888" not in result
        assert "rahul@gmail.com" not in result
        assert "9011" not in result

    def test_clean_text_unchanged(self) -> None:
        clean = "The AC unit is not cooling properly. Fan noise is audible."
        result = strip_pii(clean)
        assert "cooling" in result
        assert "Fan noise" in result
