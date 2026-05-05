"""Demo readiness check — verify the system has the right data + working LLM
calls before standing in front of judges.

Exits 0 if everything is in order, 1 if any check fails.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

# Make sure the script can be run via `python scripts/verify_demo_data.py`
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from sqlalchemy import select, func  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.models.batch_run_log import BatchRunLog  # noqa: E402
from app.models.cluster import Cluster  # noqa: E402
from app.models.complaint import Complaint  # noqa: E402
from app.models.umap_coord import UmapCoord  # noqa: E402

API_BASE = os.environ.get("HVAC_API_BASE", "http://localhost:8000/api/v1")

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}✅{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}🟡{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"{RED}❌{RESET} {msg}")


async def check_complaints() -> tuple[bool, int]:
    sf = get_session_factory()
    async with sf() as s:
        n = (await s.execute(select(func.count()).select_from(Complaint))).scalar_one()
    if n >= 500:
        ok(f"{n} complaints loaded")
        return True, int(n)
    fail(f"Only {n} complaints — RUN: make seed")
    return False, int(n)


async def check_clusters() -> tuple[bool, int, int]:
    sf = get_session_factory()
    async with sf() as s:
        n = (await s.execute(select(func.count()).select_from(Cluster))).scalar_one()
        unlabeled = (
            await s.execute(
                select(func.count()).select_from(Cluster).where(Cluster.label.is_(None))
            )
        ).scalar_one()
    if int(n) >= 5:
        ok(f"{n} clusters found")
    else:
        fail(f"Only {n} clusters — RUN: make cluster")
        return False, int(n), int(unlabeled)
    if int(unlabeled) == 0:
        ok("All clusters have labels")
    else:
        warn(f"{unlabeled} clusters unlabeled — RUN: make label-job")
    return True, int(n), int(unlabeled)


async def check_emerging() -> bool:
    sf = get_session_factory()
    async with sf() as s:
        n = (
            await s.execute(
                select(func.count()).select_from(Cluster).where(Cluster.is_emerging.is_(True))
            )
        ).scalar_one()
    if int(n) > 0:
        ok(f"{n} emerging clusters (alert banner will populate)")
        return True
    warn("No emerging clusters — demo alert banner will be empty")
    return False


async def check_umap() -> bool:
    sf = get_session_factory()
    async with sf() as s:
        n = (await s.execute(select(func.count()).select_from(UmapCoord))).scalar_one()
    if int(n) > 0:
        ok(f"{n} UMAP coordinates ready")
        return True
    fail("No UMAP coordinates — RUN: make cluster")
    return False


async def check_silhouette() -> tuple[bool, float | None]:
    sf = get_session_factory()
    async with sf() as s:
        run = (
            await s.execute(
                select(BatchRunLog)
                .where(BatchRunLog.status == "completed")
                .order_by(BatchRunLog.completed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if run and run.silhouette_score is not None:
        ok(f"Silhouette score: {run.silhouette_score:.3f}")
        return True, float(run.silhouette_score)
    warn("No silhouette score recorded yet")
    return False, None


async def check_advisory() -> bool:
    sf = get_session_factory()
    async with sf() as s:
        cluster = (
            await s.execute(
                select(Cluster)
                .where(Cluster.is_emerging.is_(True))
                .order_by(Cluster.growth_pct_wow.desc().nullslast())
                .limit(1)
            )
        ).scalar_one_or_none()
        if cluster is None:
            cluster = (
                await s.execute(
                    select(Cluster).order_by(Cluster.member_count.desc().nullslast()).limit(1)
                )
            ).scalar_one_or_none()
    if cluster is None:
        fail("No cluster available to test advisory")
        return False

    settings = get_settings()
    if not settings.GOOGLE_API_KEY:
        fail("GOOGLE_API_KEY not set — advisory generation disabled")
        return False

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            t0 = time.perf_counter()
            r = await client.get(f"{API_BASE}/clusters/{cluster.id}/advisory")
            dur = (time.perf_counter() - t0) * 1000
        if r.status_code != 200:
            fail(f"Advisory API returned {r.status_code}: {r.text[:120]}")
            return False
        body = r.json()
        text = body.get("advisory_text") or ""
        sections = text.count("##")
        if sections < 3:
            warn(f"Advisory only has {sections} ## sections (expected 3-4)")
        ok(f"Advisory generation: OK ({dur:.0f}ms, cluster #{cluster.id})")
        return True
    except Exception as exc:
        fail(f"Advisory call failed: {exc}")
        return False


async def main() -> int:
    print("\n=== HVAC Demo Readiness Check ===\n")
    results = []
    ok1, _ = await check_complaints()
    results.append(ok1)
    ok2, *_ = await check_clusters()
    results.append(ok2)
    results.append(await check_emerging())
    results.append(await check_umap())
    results.append((await check_silhouette())[0])
    results.append(await check_advisory())

    failures = sum(1 for r in results if not r)
    print()
    if failures == 0:
        print(f"{GREEN}🟢 System is DEMO READY{RESET}")
        return 0
    print(f"{RED}🔴 System has {failures} issue{'s' if failures != 1 else ''} — fix above{RESET}")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
