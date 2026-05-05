# PII Compliance Report
Generated: 2026-05-05T18:58:17.611298
System: HVAC Complaint Intelligence System v0.1.0

## Test Results
| Test | Status | Details |
|------|--------|---------|
| `test_strips_indian_mobile[Call me on 9876543210]` | ✅ PASS |  |
| `test_strips_indian_mobile[My number is 98765 43210]` | ✅ PASS |  |
| `test_strips_indian_mobile[Reach me at +91-9876543210]` | ✅ PASS |  |
| `test_strips_indian_mobile[Contact +919876543210]` | ✅ PASS |  |
| `test_preserves_non_phone_numbers` | ✅ PASS |  |
| `test_strips_aadhaar[Aadhaar: 1234 5678 9012]` | ✅ PASS |  |
| `test_strips_aadhaar[ID: 1234-5678-9012]` | ✅ PASS |  |
| `test_strips_aadhaar[My aadhaar 123456789012]` | ✅ PASS |  |
| `test_strips_email[Email raj.kumar@gmail.com-raj.kumar@gmail.com]` | ✅ PASS |  |
| `test_strips_email[Contact me at firstname.lastname@company.co.in-firstname.lastname@company.co.in]` | ✅ PASS |  |
| `test_strips_email_in_sentence` | ✅ PASS |  |
| `test_strips_pan_card` | ✅ PASS |  |
| `test_strips_multiple_pii_types_in_one_message` | ✅ PASS |  |
| `test_complaint_signal_preserved[AC not cooling at all, call me on 9876543210-cooling]` | ✅ PASS |  |
| `test_complaint_signal_preserved[Technician raj@gmail.com never showed up-technician]` | ✅ PASS |  |
| `test_complaint_signal_preserved[Unit 1.5T-SPLIT making loud noise, Aadhaar 1234 5678 9012-noise]` | ✅ PASS |  |
| `test_idempotent_stripping[Call 9876543210 about AC not cooling]` | ✅ PASS |  |
| `test_idempotent_stripping[Email raj@test.com \u2014 compressor noise]` | ✅ PASS |  |
| `test_idempotent_stripping[Normal complaint with no PII at all]` | ✅ PASS |  |
| `test_pii_stripped_before_db_write` | ✅ PASS |  |
| `test_pii_stripped_before_gemini_call` | ✅ PASS |  |
| `test_raw_text_encrypted_in_db` | ✅ PASS |  |

## Coverage
- Total PII test cases: **22**
- Passed: **22**
- Failed: **0**

## Certification
This report certifies that the HVAC Complaint Intelligence System PII protection layer was tested on 2026-05-05 and 22/22 compliance tests passed.
