"""Tests for TrendDetector — WoW growth, emerging flag, cost exposure."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from pipeline.trend_detector import TrendDetector, TrendResult


@pytest.fixture
def detector() -> TrendDetector:
    return TrendDetector()


REFERENCE_AS_OF = datetime(2026, 4, 29, 12, 0, 0)


def _build_df(
    counts_per_cluster: dict[int, tuple[int, int]],
    as_of: datetime | None = None,
) -> pd.DataFrame:
    """DataFrame with (current_week_count, previous_week_count) per cluster.

    Current entries: 2 days back. Previous entries: 10 days back.
    Both bands sit comfortably inside their week to avoid boundary flips.
    """
    as_of = as_of or REFERENCE_AS_OF
    rows: list[dict[str, object]] = []
    for cluster_id, (current, previous) in counts_per_cluster.items():
        for i in range(current):
            rows.append({
                "cluster_id": cluster_id,
                "created_at": as_of - timedelta(days=2, minutes=i),
            })
        for i in range(previous):
            rows.append({
                "cluster_id": cluster_id,
                "created_at": as_of - timedelta(days=10, minutes=i),
            })
    return pd.DataFrame(rows)


class TestWoWGrowth:
    def test_growth_positive(self, detector: TrendDetector) -> None:
        # 20 → 30 = 50% growth → emerging
        df = _build_df({1: (30, 20)})
        result = detector.compute_trends(df, as_of=REFERENCE_AS_OF)
        assert len(result) == 1
        r = result[0]
        assert r.current_week_count == 30
        assert r.previous_week_count == 20
        assert r.growth_pct == pytest.approx(50.0)
        assert r.is_emerging is True

    def test_growth_negative(self, detector: TrendDetector) -> None:
        # 30 → 20 ≈ -33% → not emerging
        df = _build_df({1: (20, 30)})
        result = detector.compute_trends(df, as_of=REFERENCE_AS_OF)
        r = result[0]
        assert r.growth_pct == pytest.approx(-33.333333, abs=0.01)
        assert r.is_emerging is False

    def test_growth_zero_previous(self, detector: TrendDetector) -> None:
        # 0 → 10 = 100% (special case)
        df = _build_df({1: (10, 0)})
        result = detector.compute_trends(df, as_of=REFERENCE_AS_OF)
        r = result[0]
        assert r.growth_pct == 100.0
        assert r.is_emerging is True

    def test_growth_below_emerging_threshold(self, detector: TrendDetector) -> None:
        # 10 → 12 = 20% < 30% → not emerging
        df = _build_df({1: (12, 10)})
        result = detector.compute_trends(df, as_of=REFERENCE_AS_OF)
        r = result[0]
        assert r.growth_pct == pytest.approx(20.0)
        assert r.is_emerging is False


class TestCostExposure:
    def test_window_cost_exposure_default(self, detector: TrendDetector) -> None:
        # cluster size 23 × 8500 = 195_500
        df = _build_df({1: (15, 8)})
        result = detector.compute_trends(df, as_of=REFERENCE_AS_OF)
        r = result[0]
        assert r.window_cost_exposure == pytest.approx(195_500.0)

    def test_window_cost_exposure_custom(self) -> None:
        det = TrendDetector(warranty_cost=10_000.0)
        df = _build_df({1: (5, 5)})
        result = det.compute_trends(df)
        r = result[0]
        assert r.window_cost_exposure == pytest.approx(100_000.0)

    def test_default_warranty_cost(self) -> None:
        assert TrendDetector.DEFAULT_WARRANTY_COST == 8500.0


class TestLookbackFilter:
    def test_old_complaints_excluded(self, detector: TrendDetector) -> None:
        as_of = datetime(2026, 4, 29, 12, 0, 0)
        df = _build_df({1: (5, 5)}, as_of=as_of)
        ancient = pd.DataFrame([
            {"cluster_id": 1, "created_at": as_of - timedelta(days=60)}
            for _ in range(10)
        ])
        df = pd.concat([df, ancient], ignore_index=True)
        result = detector.compute_trends(df, lookback_days=30, as_of=as_of)
        r = result[0]
        # filtered cluster size = 10 (5 current + 5 prev), not 20
        assert r.window_cost_exposure == pytest.approx(10 * 8500.0)


class TestNoiseAndEmpty:
    def test_noise_cluster_excluded(self, detector: TrendDetector) -> None:
        df = _build_df({-1: (5, 5), 0: (10, 5)})
        result = detector.compute_trends(df, as_of=REFERENCE_AS_OF)
        ids = [r.cluster_id for r in result]
        assert -1 not in ids
        assert 0 in ids

    def test_empty_df_returns_empty(self, detector: TrendDetector) -> None:
        result = detector.compute_trends(pd.DataFrame())
        assert result == []

    def test_returns_trend_result(self, detector: TrendDetector) -> None:
        df = _build_df({1: (5, 5)})
        result = detector.compute_trends(df, as_of=REFERENCE_AS_OF)
        assert isinstance(result[0], TrendResult)
