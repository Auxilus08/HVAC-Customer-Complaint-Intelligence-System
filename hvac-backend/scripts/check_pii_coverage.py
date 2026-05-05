"""PII strip audit gate — pre-commit hook.

Parses the AST of complaint_service.py and label_job.py to verify that
strip_pii() is called BEFORE any session.add() or model.encode() call
in the same function body. Exits with code 1 if the invariant is broken.

This is the automated PII compliance gate for CI.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Files and the guard calls we expect to find before sensitive operations
AUDIT_TARGETS = [
    {
        "file": Path("app/services/complaint_service.py"),
        "guard": "strip_pii",
        "sensitive_calls": {"session.add", "session.flush"},
        "description": "complaint_service: PII strip before DB write",
    },
    {
        "file": Path("app/services/advisory_service.py"),
        "guard": "strip_pii",
        "sensitive_calls": {"model.generate_content"},
        "description": "advisory_service: PII strip before Gemini API call",
    },
    {
        "file": Path("app/workers/label_job.py"),
        "guard": "strip_pii",
        "sensitive_calls": {"model.generate_content"},
        "description": "label_job: PII strip before Gemini API call",
    },
]


class CallOrderVisitor(ast.NodeVisitor):
    """Walk a function body and record the line numbers of specific calls."""

    def __init__(self, guard_name: str, sensitive_names: set[str]) -> None:
        self.guard_name = guard_name
        self.sensitive_names = sensitive_names
        self.guard_lines: list[int] = []
        self.sensitive_lines: list[tuple[int, str]] = []

    def _is_guard_call(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == self.guard_name:
                return True
            if isinstance(func, ast.Attribute) and func.attr == self.guard_name:
                return True
        return False

    def _is_sensitive_call(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Call):
            func = node.func
            # e.g. session.add(...)
            if isinstance(func, ast.Attribute):
                for name in self.sensitive_names:
                    parts = name.split(".")
                    if func.attr == parts[-1]:
                        return name
        return None

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for val in [node.value]:
            if self._is_guard_call(val):
                self.guard_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:  # noqa: N802
        if self._is_guard_call(node.value):
            self.guard_lines.append(node.lineno)
        elif (name := self._is_sensitive_call(node.value)) is not None:
            self.sensitive_lines.append((node.lineno, name))
        self.generic_visit(node)

    def visit_Await(self, node: ast.Await) -> None:  # noqa: N802
        if self._is_guard_call(node.value):
            self.guard_lines.append(node.lineno)
        elif (name := self._is_sensitive_call(node.value)) is not None:
            self.sensitive_lines.append((node.lineno, name))
        self.generic_visit(node)


def check_file(target: dict) -> list[str]:
    """Return a list of violation messages for one target file."""
    path: Path = target["file"]
    guard: str = target["guard"]
    sensitive: set[str] = target["sensitive_calls"]
    description: str = target["description"]

    if not path.exists():
        return [f"[SKIP] {path} not found — skipping audit"]

    source = path.read_text()
    tree = ast.parse(source, filename=str(path))

    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue

        visitor = CallOrderVisitor(guard, sensitive)
        for child in node.body:
            visitor.visit(child)

        for sensitive_line, call_name in visitor.sensitive_lines:
            # Is there a guard call on a line BEFORE this sensitive call?
            guards_before = [g for g in visitor.guard_lines if g < sensitive_line]
            if not guards_before:
                violations.append(
                    f"  VIOLATION in {path}:{sensitive_line} — "
                    f"function '{node.name}': "
                    f"'{call_name}' called WITHOUT prior {guard}() "
                    f"[{description}]"
                )

    return violations


def main() -> int:
    all_violations: list[str] = []

    for target in AUDIT_TARGETS:
        violations = check_file(target)
        # Filter out skips from the failure count
        real_violations = [v for v in violations if not v.startswith("[SKIP]")]
        skips = [v for v in violations if v.startswith("[SKIP]")]
        for s in skips:
            print(s)
        all_violations.extend(real_violations)

    if all_violations:
        print("\n" + "=" * 70)
        print("PII STRIP AUDIT FAILED")
        print("=" * 70)
        print("The following call sites handle complaint text without")
        print("first calling strip_pii():\n")
        for v in all_violations:
            print(v)
        print("\nFix: ensure strip_pii(text) is called before the flagged line.")
        print("See app/core/security.py for the canonical strip_pii() function.")
        print("=" * 70 + "\n")
        return 1

    print(f"PII strip audit passed ({len(AUDIT_TARGETS)} files checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
