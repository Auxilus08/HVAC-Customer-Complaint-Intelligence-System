#!/usr/bin/env python3
"""Pre-commit hook: fail if print() statements exist in app/ source files."""
import glob
import sys

files = glob.glob("app/**/*.py", recursive=True)
found = []
for path in files:
    with open(path) as fh:
        for i, line in enumerate(fh, 1):
            stripped = line.lstrip()
            if stripped.startswith("print(") and not stripped.startswith("#"):
                found.append(f"{path}:{i}: {line.rstrip()}")

if found:
    print("ERROR: print() statements found (use structlog instead):")
    print("\n".join(found))
    sys.exit(1)
