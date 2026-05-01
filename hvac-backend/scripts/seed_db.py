"""Seed the database with synthetic complaints from hvac-ml generated data.

Usage:
    python scripts/seed_db.py [--csv PATH] [--limit N]

Defaults to ../../hvac-ml/data/generated/complaints_500.csv.
PII stripping is applied before DB write, matching production behaviour.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path

# Ensure the backend package is importable when run from scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))


async def seed(csv_path: Path, limit: int) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import get_settings
    from app.core.security import strip_pii
    from app.db.session import init_db
    from app.models.complaint import Complaint

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    await init_db()

    rows: list[dict[str, str]] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            if i >= limit:
                break
            rows.append(row)

    async with factory() as session:
        for row in rows:
            raw_text = row.get("complaint_text") or row.get("text", "")
            if not raw_text.strip():
                continue
            clean_text = strip_pii(raw_text)
            complaint = Complaint(
                clean_text=clean_text,
                source=row.get("source") or None,
                region=row.get("region") or None,
                product_sku=row.get("product_sku") or None,
                status="pending",
            )
            session.add(complaint)
        await session.commit()

    print(f"Seeded {len(rows)} complaints from {csv_path}")
    await engine.dispose()


def main() -> None:
    default_csv = (
        Path(__file__).parent.parent.parent / "hvac-ml" / "data" / "generated" / "complaints_500.csv"
    )
    parser = argparse.ArgumentParser(description="Seed DB with synthetic complaints")
    parser.add_argument("--csv", type=Path, default=default_csv)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(seed(args.csv, args.limit))


if __name__ == "__main__":
    main()
