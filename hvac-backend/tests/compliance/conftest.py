"""Compliance pytest plugin — emits a Markdown audit report after the run."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

REPORT_DIR = Path(__file__).parent / "reports"


def pytest_configure(config: pytest.Config) -> None:
    config._compliance_results: list[tuple[str, str, str]] = []  # type: ignore[attr-defined]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Any, call: Any):
    outcome = yield
    rep = outcome.get_result()
    if rep.when != "call":
        return
    if "compliance" not in item.keywords:
        return
    status = "PASS" if rep.passed else ("FAIL" if rep.failed else "SKIP")
    detail = "" if rep.passed else (rep.longreprtext.splitlines()[-1] if rep.longrepr else "")
    item.config._compliance_results.append((item.name, status, detail))  # type: ignore[attr-defined]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    results: list[tuple[str, str, str]] = getattr(session.config, "_compliance_results", [])
    if not results:
        return
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    out = REPORT_DIR / f"pii_compliance_{date}.md"

    total = len(results)
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")

    lines = [
        "# PII Compliance Report",
        f"Generated: {datetime.now().isoformat()}",
        "System: HVAC Complaint Intelligence System v0.1.0",
        "",
        "## Test Results",
        "| Test | Status | Details |",
        "|------|--------|---------|",
    ]
    for name, status, detail in results:
        emoji = "✅" if status == "PASS" else ("❌" if status == "FAIL" else "⚠️")
        lines.append(f"| `{name}` | {emoji} {status} | {detail} |")
    lines += [
        "",
        "## Coverage",
        f"- Total PII test cases: **{total}**",
        f"- Passed: **{passed}**",
        f"- Failed: **{failed}**",
        "",
        "## Certification",
        f"This report certifies that the HVAC Complaint Intelligence System PII "
        f"protection layer was tested on {date} and {passed}/{total} compliance "
        f"tests passed.",
        "",
    ]
    out.write_text("\n".join(lines))
    print(f"\n[compliance] report → {out}")
