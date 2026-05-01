"""Week-over-week growth + cost exposure detection per cluster.

Single source of truth for trend math. hvac-backend's trend_job MUST
import TrendDetector from here — no local re-implementation.

Definitions:
    growth_pct       (current - previous) / previous * 100, with the
                     special case previous == 0 → growth = 100.0.
    is_emerging      True when growth_pct > EMERGING_GROWTH_PCT (30%).
    window_cost_exposure  cluster_size * warranty_cost (Rs.) over the
                         lookback_days window only — not lifetime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

EMERGING_GROWTH_PCT: float = 30.0


@dataclass
class TrendResult:
    cluster_id: int
    current_week_count: int
    previous_week_count: int
    growth_pct: float
    is_emerging: bool
    window_cost_exposure: float


class TrendDetector:
    """Calculates week-over-week growth, emerging flag, and cost exposure.

    Args:
        warranty_cost: Average warranty cost (Rs.) per complaint. Defaults to
            DEFAULT_WARRANTY_COST.
    """

    DEFAULT_WARRANTY_COST: float = 8500.0

    def __init__(self, warranty_cost: float | None = None) -> None:
        self.warranty_cost = (
            warranty_cost if warranty_cost is not None else self.DEFAULT_WARRANTY_COST
        )

    # ── Public API ─────────────────────────────────────────────────────────
    def compute_trends(
        self,
        df: pd.DataFrame,
        lookback_days: int = 30,
        as_of: date | datetime | None = None,
    ) -> list[TrendResult]:
        """Compute trend stats per cluster.

        Args:
            df:             DataFrame with columns ``cluster_id`` and
                            ``created_at`` (any pandas-parseable timestamp).
            lookback_days:  Filter window — complaints older than this are
                            dropped before any aggregation.
            as_of:          Reference "now". Defaults to the most recent
                            ``created_at`` in *df*, falling back to today.

        Returns: list of TrendResult, one per cluster (excluding noise -1).
        """
        if df.empty or "cluster_id" not in df.columns:
            return []

        df = df.copy()
        df["created_at"] = pd.to_datetime(df["created_at"], utc=False, errors="coerce")
        if df["created_at"].dt.tz is not None:
            df["created_at"] = df["created_at"].dt.tz_convert(None).dt.tz_localize(None)
        df = df.dropna(subset=["created_at"])

        if as_of is None:
            as_of_ts = df["created_at"].max()
        else:
            as_of_ts = pd.Timestamp(as_of)

        cutoff = as_of_ts - pd.Timedelta(days=lookback_days)
        df = df[df["created_at"] >= cutoff]

        results: list[TrendResult] = []
        for cluster_id, group in df.groupby("cluster_id"):
            cid_int = int(cluster_id)
            if cid_int == -1:
                continue

            current_start = as_of_ts - pd.Timedelta(days=7)
            previous_start = as_of_ts - pd.Timedelta(days=14)

            current_count = int(
                ((group["created_at"] >= current_start)
                 & (group["created_at"] <= as_of_ts)).sum()
            )
            previous_count = int(
                ((group["created_at"] >= previous_start)
                 & (group["created_at"] < current_start)).sum()
            )

            growth_pct = self._wow_growth_pct(current_count, previous_count)
            is_emerging = growth_pct > EMERGING_GROWTH_PCT
            cluster_size = len(group)
            # Cost over lookback_days window only — not lifetime cluster exposure.
            window_cost_exposure = float(cluster_size) * self.warranty_cost

            results.append(
                TrendResult(
                    cluster_id=cid_int,
                    current_week_count=current_count,
                    previous_week_count=previous_count,
                    growth_pct=growth_pct,
                    is_emerging=is_emerging,
                    window_cost_exposure=window_cost_exposure,
                )
            )

        logger.info(
            "trend_detector_complete",
            clusters=len(results),
            emerging=sum(1 for r in results if r.is_emerging),
        )
        return results

    # ── Math helper ────────────────────────────────────────────────────────
    @staticmethod
    def _wow_growth_pct(current: int, previous: int) -> float:
        """Week-over-week growth in percent.

        previous == 0 is the "anything new is a 100% jump" case.
        All cost calculations use the lookback window, not lifetime cluster size.
        """
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return (current - previous) / previous * 100.0

    # Backwards-compatible alias for the spec's `_wow_growth` name.
    def _wow_growth(self, weekly_counts: pd.Series) -> float:
        if len(weekly_counts) < 2:
            return 0.0
        prev = int(weekly_counts.iloc[-2])
        cur = int(weekly_counts.iloc[-1])
        return self._wow_growth_pct(cur, prev)
