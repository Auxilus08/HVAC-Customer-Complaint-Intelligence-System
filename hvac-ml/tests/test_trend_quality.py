"""Trend detection quality gates — Track B3."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from pipeline.trend_detector import TrendDetector

pytestmark = pytest.mark.slow


def test_cost_exposure_calculation():
    """cost_exposure should equal complaint_count × warranty_cost."""
    today = datetime.now()
    rows = [{"cluster_id": 1, "created_at": today - timedelta(days=i % 7)} for i in range(23)]
    df = pd.DataFrame(rows)
    detector = TrendDetector(warranty_cost=8500.0)
    trends = detector.compute_trends(df)
    cluster_1 = next(t for t in trends if t.cluster_id == 1)
    assert cluster_1.window_cost_exposure == pytest.approx(23 * 8500.0)


def test_wow_growth_boundary_conditions():
    """Static helper must handle 0/N, N/0, and standard ratios."""
    fn = TrendDetector._wow_growth_pct.__func__ if hasattr(TrendDetector._wow_growth_pct, "__func__") else TrendDetector._wow_growth_pct
    # 0 → 10 = +infinite/cap. Implementation choice — must be > 0 and not raise.
    g = fn(10, 0)
    assert isinstance(g, float)
    assert g > 0
    # 10 → 0 = -100%
    g = fn(0, 10)
    assert g == pytest.approx(-100.0)
    # 10 → 20 = +100%
    g = fn(20, 10)
    assert g == pytest.approx(100.0)
    # 20 → 10 = -50%
    g = fn(10, 20)
    assert g == pytest.approx(-50.0)


def test_emerging_flag_set_on_growth_spike():
    """A 5x week-over-week growth must surface at least one emerging cluster."""
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    rows: list[dict] = []
    # Calm cluster — steady 5/week
    for w in range(2):
        for _ in range(5):
            rows.append({"cluster_id": 99, "created_at": today - timedelta(days=w * 7 + 1)})
    # Spike cluster — 2 last week, 20 this week
    for _ in range(2):
        rows.append({"cluster_id": 1, "created_at": week_ago - timedelta(days=2)})
    for _ in range(20):
        rows.append({"cluster_id": 1, "created_at": today - timedelta(days=1)})

    df = pd.DataFrame(rows)
    trends = TrendDetector().compute_trends(df, lookback_days=30, as_of=today)
    spike = next(t for t in trends if t.cluster_id == 1)
    assert spike.growth_pct > 100, f"spike growth {spike.growth_pct} not detected"
    emerging = [t for t in trends if t.is_emerging]
    assert len(emerging) >= 1, "no cluster flagged emerging on a 10x spike"
