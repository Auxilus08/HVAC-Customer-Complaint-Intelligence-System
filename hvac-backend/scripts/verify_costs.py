"""Verify the new multi-market tiered cost model results."""
import asyncio, sys, os
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://hvac:hvac@db:5432/hvac")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text


async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with AsyncSession(engine) as session:

        # Top 10 clusters that actually have complaints right now
        rows = (await session.execute(text(
            "SELECT c.id, c.label, c.member_count, c.cost_exposure_estimate, "
            "       c.is_emerging, c.growth_pct_wow, "
            "       COUNT(co.id) as actual_count "
            "FROM clusters c "
            "JOIN complaints co ON co.cluster_id = c.id "
            "GROUP BY c.id, c.label, c.member_count, "
            "         c.cost_exposure_estimate, c.is_emerging, c.growth_pct_wow "
            "ORDER BY c.cost_exposure_estimate DESC "
            "LIMIT 12"
        ))).fetchall()

        print("Top 12 clusters by cost exposure (USD) — tiered model:")
        print(f"{'ID':>4}  {'Count':>5}  {'Cost (USD)':>12}  {'$/complaint':>12}  {'Emerging':>8}  {'WoW':>6}  Label")
        print("-" * 90)
        for r in rows:
            cid, label, mc, cost, emerging, wow, cnt = r
            cost_f = float(cost)
            per = cost_f / cnt if cnt else 0
            em = "YES" if emerging else "-"
            wow_s = f"{float(wow):+.0f}%" if wow is not None else "—"
            print(f"{cid:>4}  {cnt:>5}  ${cost_f:>11,.0f}  ${per:>11,.0f}  {em:>8}  {wow_s:>6}  {label}")

        print()

        # Per-market cost breakdown to verify correctness
        rows2 = (await session.execute(text(
            "SELECT "
            "  CASE "
            "    WHEN LOWER(co.region) IN ('bronx','brooklyn','manhattan','queens','staten island','nyc') THEN 'USA ($250 base)' "
            "    WHEN co.region IN ('Delhi','Mumbai','Bangalore','Chennai','Hyderabad','Kolkata','Pune','Ahmedabad','Gurgaon','Noida') THEN 'India ($30 base)' "
            "    ELSE 'Other/Unknown ($120 base)' "
            "  END as market, "
            "  co.sentiment_label, "
            "  COUNT(*) as cnt "
            "FROM complaints co "
            "WHERE co.cluster_id IS NOT NULL "
            "GROUP BY 1, 2 ORDER BY 1, cnt DESC"
        ))).fetchall()

        print("Complaint breakdown by market + sentiment (cost model inputs):")
        print(f"  {'Market':<28}  {'Label':<10}  {'Count':>6}")
        print("  " + "-" * 50)
        for r in rows2:
            print(f"  {r[0]:<28}  {str(r[1]):<10}  {r[2]:>6}")

        # Zero out stale clusters that have no complaints
        stale = (await session.execute(text(
            "UPDATE clusters SET cost_exposure_estimate = 0, member_count = 0 "
            "WHERE id NOT IN (SELECT DISTINCT cluster_id FROM complaints WHERE cluster_id IS NOT NULL) "
            "RETURNING id"
        ))).fetchall()
        await session.commit()
        print(f"\nZeroed out {len(stale)} stale clusters with no complaints.")

        # Total system cost exposure
        total = (await session.execute(text(
            "SELECT SUM(cost_exposure_estimate) FROM clusters"
        ))).scalar()
        print(f"Total system cost exposure: ${float(total):,.0f} USD")


asyncio.run(main())
