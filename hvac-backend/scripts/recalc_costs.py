"""One-shot script: recalculate cost_exposure_estimate for all clusters
using the new multi-market tiered cost model in TrendDetector."""
import asyncio
import sys
import os
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd

sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://hvac:hvac@db:5432/hvac")


async def main():
    from pipeline.trend_detector import TrendDetector
    from app.config import get_settings
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import text

    settings = get_settings()
    engine = create_async_engine(os.environ["DATABASE_URL"])

    async with AsyncSession(engine) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT cluster_id, created_at, sentiment_score, "
                    "sentiment_label, region "
                    "FROM complaints "
                    "WHERE cluster_id IS NOT NULL AND cluster_id != -1"
                )
            )
        ).fetchall()
        print(f"Loaded {len(rows)} complaints")

        df = pd.DataFrame(
            rows,
            columns=["cluster_id", "created_at", "sentiment_score",
                     "sentiment_label", "region"],
        )

        detector = TrendDetector()
        trends = detector.compute_trends(
            df, lookback_days=30, as_of=datetime.now(UTC)
        )
        by_id = {t.cluster_id: t for t in trends}
        print(f"Computed trends for {len(trends)} clusters (region-aware + tiered)")

        grp = df.groupby("cluster_id")
        avg_sent = grp["sentiment_score"].mean().to_dict()
        counts = grp.size().to_dict()

        cluster_ids = (
            await session.execute(text("SELECT id FROM clusters"))
        ).scalars().all()

        min_alert = getattr(settings, "MIN_COMPLAINTS_FOR_ALERT", 3)
        updated = emerging = 0

        for cid in cluster_ids:
            t = by_id.get(cid)
            if t is None:
                await session.execute(
                    text(
                        "UPDATE clusters SET growth_pct_wow=0, is_emerging=false, "
                        "member_count=0, cost_exposure_estimate=0 WHERE id=:id"
                    ),
                    {"id": cid},
                )
                continue

            is_emerging = t.is_emerging and t.current_week_count >= min_alert
            sentiment = (
                float(avg_sent[cid]) if pd.notna(avg_sent.get(cid)) else None
            )

            await session.execute(
                text(
                    "UPDATE clusters SET "
                    "growth_pct_wow=:growth, is_emerging=:em, "
                    "avg_sentiment=:sent, cost_exposure_estimate=:cost, "
                    "member_count=:cnt "
                    "WHERE id=:id"
                ),
                {
                    "growth": float(t.growth_pct),
                    "em": is_emerging,
                    "sent": sentiment,
                    "cost": Decimal(str(t.window_cost_exposure)),
                    "cnt": int(counts.get(cid, 0)),
                    "id": cid,
                },
            )
            updated += 1
            if is_emerging:
                emerging += 1

        # Zero out clusters that have no complaints in current data
        # so stale member_count / cost_exposure from old runs don't persist.
        stale = (
            await session.execute(
                text(
                    "UPDATE clusters SET cost_exposure_estimate = 0, member_count = 0 "
                    "WHERE id NOT IN ("
                    "  SELECT DISTINCT cluster_id FROM complaints "
                    "  WHERE cluster_id IS NOT NULL"
                    ") RETURNING id"
                )
            )
        ).fetchall()

        await session.commit()
        print(f"Updated {updated} clusters, {emerging} emerging, zeroed {len(stale)} stale")

        sample = (
            await session.execute(
                text(
                    "SELECT id, label, member_count, cost_exposure_estimate "
                    "FROM clusters ORDER BY cost_exposure_estimate DESC LIMIT 10"
                )
            )
        ).fetchall()
        print("\nTop 10 by cost exposure (USD):")
        for r in sample:
            print(f"  id={r[0]:3d}  count={r[2]:3d}  cost=${float(r[3]):>10,.0f}  {r[1]}")

        mkt = (
            await session.execute(
                text(
                    "SELECT "
                    "CASE "
                    "WHEN LOWER(region) IN ('bronx','brooklyn','manhattan','queens','staten island','nyc') THEN 'USA' "
                    "WHEN region IN ('Delhi','Mumbai','Bangalore','Chennai','Hyderabad','Kolkata','Pune','Ahmedabad','Gurgaon','Noida') THEN 'India' "
                    "ELSE 'Other' END as market, "
                    "COUNT(*) as n, AVG(sentiment_score) as s "
                    "FROM complaints WHERE cluster_id IS NOT NULL "
                    "GROUP BY 1 ORDER BY 2 DESC"
                )
            )
        ).fetchall()
        print("\nComplaint market split:")
        for r in mkt:
            print(f"  {r[0]}: {r[1]} complaints, avg_sentiment={float(r[2]):.3f}")


asyncio.run(main())
