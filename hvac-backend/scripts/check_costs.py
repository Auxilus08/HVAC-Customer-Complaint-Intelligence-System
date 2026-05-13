import asyncio, sys, os
sys.path.insert(0, '/app')
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://hvac:hvac@db:5432/hvac')
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

async def check():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with AsyncSession(engine) as session:
        r = await session.execute(text(
            "SELECT c.id, c.label, c.cost_exposure_estimate, COUNT(co.id) as n "
            "FROM clusters c JOIN complaints co ON co.cluster_id = c.id "
            "GROUP BY c.id, c.label, c.cost_exposure_estimate "
            "ORDER BY c.cost_exposure_estimate DESC LIMIT 10"
        ))
        print('Top 10 by new cost (clusters with real complaints):')
        for row in r.fetchall():
            per = float(row[2]) / row[3] if row[3] else 0
            print(f'  id={row[0]:3d} cnt={row[3]:3d} cost=${float(row[2]):>10,.0f}  avg/complaint=${per:,.0f}  {row[1]}')

asyncio.run(check())
