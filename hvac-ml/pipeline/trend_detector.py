"""Week-over-week growth + cost exposure detection per cluster.

Single source of truth for trend math. hvac-backend's trend_job MUST
import TrendDetector from here — no local re-implementation.

Definitions:
    growth_pct           (current - previous) / previous * 100, with the
                         special case previous == 0 → growth = 100.0.
    is_emerging          True when growth_pct > EMERGING_GROWTH_PCT (30%).
    window_cost_exposure Sum of per-complaint cost estimates (USD) over the
                         lookback_days window.

Cost model — tiered by market + fault severity
────────────────────────────────────────────────
Each complaint's cost  =  BASE_COST[market]  ×  SEVERITY_MULT[sentiment_label]

Base costs in USD (service call + minor parts, 2025-2026 market data):
  USA          $250  (HomeAdvisor/Angi avg: $130–$2,000 range; $350 median)
  Canada       $200  (CAD ~$270; similar labour structure to US)
  Europe       $200  (€185; Germany/UK/France field service benchmarks)
  Australia    $180  (AUD ~$270; comparable to Europe)
  Middle East  $150  (AED 550 / SAR 560; Dubai/Riyadh service market)
  Latin Am.    $80   (MXN 1,400 / BRL 400; Mexico City / São Paulo)
  China        $60   (¥430; Carrier China service call benchmark)
  SE Asia      $60   (SGD 80 / THB 2,200; Singapore / Bangkok)
  India        $30   (₹2,500; NoBroker / Urban Company / Carrier AMC data)
  Default      $120  (conservative global midpoint for unclassified regions)

Severity multipliers (actuarial Pareto 80/20 — universal across all markets):
  CRITICAL  × 8.0   compressor failure, major refrigerant leak
  HIGH      × 3.5   sensor/electrical fault, minor refrigerant leak
  NORMAL    × 1.0   routine maintenance, filter, cleaning
  POSITIVE  × 0.5   informational / no hardware involved
  unknown   × 1.5   no label available — conservative midpoint

Emerging-cluster penalty × 1.2:
  Systemic faults drive coordinated response — senior-tech dispatch,
  parts procurement at scale, root-cause investigation overhead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

EMERGING_GROWTH_PCT: float = 30.0

# ── Market base costs (USD) ───────────────────────────────────────────────────

_MARKET_BASE_USD: dict[str, float] = {
    "usa":          250.0,
    "canada":       200.0,
    "europe":       200.0,
    "australia":    180.0,
    "middle_east":  150.0,
    "latin_am":      80.0,
    "china":         60.0,
    "se_asia":       60.0,
    "india":         30.0,
    "default":      120.0,
}

# Keyword → market key. Checked case-insensitively against the region field.
# Longer / more specific entries should come first within each market group.
_REGION_MARKET_MAP: list[tuple[str, str]] = [
    # USA
    ("bronx",         "usa"), ("brooklyn",    "usa"), ("manhattan",   "usa"),
    ("queens",        "usa"), ("staten island","usa"), ("nyc",         "usa"),
    ("new york",      "usa"), ("los angeles",  "usa"), ("chicago",     "usa"),
    ("houston",       "usa"), ("phoenix",      "usa"), ("philadelphia","usa"),
    ("san antonio",   "usa"), ("dallas",       "usa"), ("san diego",   "usa"),
    ("san jose",      "usa"), ("austin",       "usa"), ("jacksonville","usa"),
    ("fort worth",    "usa"), ("columbus",     "usa"), ("charlotte",   "usa"),
    ("indianapolis",  "usa"), ("san francisco","usa"), ("seattle",     "usa"),
    ("denver",        "usa"), ("nashville",    "usa"), ("oklahoma",    "usa"),
    ("el paso",       "usa"), ("washington",   "usa"), ("boston",      "usa"),
    ("memphis",       "usa"), ("louisville",   "usa"), ("portland",    "usa"),
    ("las vegas",     "usa"), ("miami",        "usa"), ("atlanta",     "usa"),
    # Canada
    ("toronto",    "canada"), ("vancouver",  "canada"), ("montreal",  "canada"),
    ("calgary",    "canada"), ("ottawa",     "canada"), ("edmonton",  "canada"),
    # Europe
    ("london",     "europe"), ("paris",      "europe"), ("berlin",    "europe"),
    ("madrid",     "europe"), ("rome",       "europe"), ("amsterdam", "europe"),
    ("barcelona",  "europe"), ("vienna",     "europe"), ("warsaw",    "europe"),
    ("brussels",   "europe"), ("stockholm",  "europe"), ("milan",     "europe"),
    ("munich",     "europe"), ("zurich",     "europe"), ("lisbon",    "europe"),
    ("prague",     "europe"), ("budapest",   "europe"), ("athens",    "europe"),
    ("rotterdam",  "europe"), ("hamburg",    "europe"), ("frankfurt", "europe"),
    # Australia / NZ
    ("sydney",     "australia"), ("melbourne", "australia"), ("brisbane",  "australia"),
    ("perth",      "australia"), ("adelaide",  "australia"), ("auckland",  "australia"),
    # Middle East
    ("dubai",      "middle_east"), ("abu dhabi", "middle_east"), ("riyadh",    "middle_east"),
    ("jeddah",     "middle_east"), ("doha",      "middle_east"), ("kuwait",    "middle_east"),
    ("muscat",     "middle_east"), ("manama",    "middle_east"), ("sharjah",   "middle_east"),
    ("cairo",      "middle_east"), ("amman",     "middle_east"), ("beirut",    "middle_east"),
    # Latin America
    ("mexico",     "latin_am"), ("mexico city", "latin_am"), ("sao paulo",    "latin_am"),
    ("bogota",     "latin_am"), ("santiago",    "latin_am"), ("lima",          "latin_am"),
    ("buenos aires","latin_am"), ("rio",         "latin_am"), ("medellin",     "latin_am"),
    # China
    ("beijing",    "china"), ("shanghai",  "china"), ("guangzhou", "china"),
    ("shenzhen",   "china"), ("chengdu",   "china"), ("wuhan",     "china"),
    ("xian",       "china"), ("hangzhou",  "china"), ("nanjing",   "china"),
    ("tianjin",    "china"), ("chongqing", "china"),
    # SE Asia
    ("singapore",  "se_asia"), ("bangkok",     "se_asia"), ("kuala lumpur", "se_asia"),
    ("jakarta",    "se_asia"), ("manila",      "se_asia"), ("ho chi minh",  "se_asia"),
    ("hanoi",      "se_asia"), ("yangon",      "se_asia"), ("phnom penh",   "se_asia"),
    ("colombo",    "se_asia"),
    # India
    ("delhi",      "india"), ("mumbai",    "india"), ("bangalore",  "india"),
    ("bengaluru",  "india"), ("hyderabad", "india"), ("chennai",    "india"),
    ("kolkata",    "india"), ("pune",      "india"), ("ahmedabad",  "india"),
    ("gurgaon",    "india"), ("gurugram",  "india"), ("noida",      "india"),
    ("surat",      "india"), ("jaipur",    "india"), ("lucknow",    "india"),
    ("kanpur",     "india"), ("nagpur",    "india"), ("indore",     "india"),
    ("thane",      "india"), ("bhopal",    "india"), ("patna",      "india"),
]


def classify_market(region: str | None) -> str:
    """Return the market key for a region string, or 'default'."""
    if not region or not isinstance(region, str):
        return "default"
    lower = region.strip().lower()
    for keyword, market in _REGION_MARKET_MAP:
        if keyword in lower:
            return market
    return "default"


def base_cost_usd(region: str | None) -> float:
    """Return the base service-call cost in USD for a region."""
    return _MARKET_BASE_USD[classify_market(region)]


# ── Severity multipliers (universal) ─────────────────────────────────────────

SENTIMENT_COST_MULTIPLIERS: dict[str, float] = {
    "CRITICAL": 8.0,
    "HIGH":     3.5,
    "NORMAL":   1.0,
    "POSITIVE": 0.5,
}
_UNKNOWN_MULTIPLIER: float = 1.5

EMERGING_CLUSTER_COST_PENALTY: float = 1.2


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TrendResult:
    cluster_id: int
    current_week_count: int
    previous_week_count: int
    growth_pct: float
    is_emerging: bool
    window_cost_exposure: float


# ── TrendDetector ─────────────────────────────────────────────────────────────

class TrendDetector:
    """Calculates week-over-week growth, emerging flag, and cost exposure.

    The ``warranty_cost`` constructor argument is kept for backward
    compatibility. It is only used when the DataFrame has no
    ``sentiment_label`` column (legacy flat-rate fallback).
    """

    DEFAULT_WARRANTY_COST: float = _MARKET_BASE_USD["default"]

    def __init__(self, warranty_cost: float | None = None) -> None:
        self._legacy_flat_cost = (
            warranty_cost if warranty_cost is not None else self.DEFAULT_WARRANTY_COST
        )

    def compute_trends(
        self,
        df: pd.DataFrame,
        lookback_days: int = 30,
        as_of: date | datetime | None = None,
    ) -> list[TrendResult]:
        """Compute trend stats per cluster.

        Args:
            df:             DataFrame with at minimum columns ``cluster_id``
                            and ``created_at``. Optional columns used when
                            present: ``sentiment_label`` (tiered cost model),
                            ``region`` (market-aware base cost).
            lookback_days:  Filter window in days.
            as_of:          Reference "now". Defaults to max(created_at).

        Returns: list of TrendResult, one per cluster (excluding noise -1).
        """
        if df.empty or "cluster_id" not in df.columns:
            return []

        df = df.copy()
        df["created_at"] = pd.to_datetime(df["created_at"], utc=False, errors="coerce")
        if df["created_at"].dt.tz is not None:
            df["created_at"] = df["created_at"].dt.tz_convert(None).dt.tz_localize(None)
        df = df.dropna(subset=["created_at"])

        has_labels  = "sentiment_label" in df.columns
        has_regions = "region" in df.columns

        if as_of is None:
            as_of_ts = df["created_at"].max()
        else:
            as_of_ts = pd.Timestamp(as_of)
            if as_of_ts.tz is not None:
                as_of_ts = as_of_ts.tz_localize(None)

        cutoff = as_of_ts - pd.Timedelta(days=lookback_days)
        df = df[df["created_at"] >= cutoff]

        results: list[TrendResult] = []
        for cluster_id, group in df.groupby("cluster_id"):
            cid_int = int(cluster_id)
            if cid_int == -1:
                continue

            current_start  = as_of_ts - pd.Timedelta(days=7)
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

            cost = self._compute_cost(group, is_emerging, has_labels, has_regions)

            results.append(TrendResult(
                cluster_id=cid_int,
                current_week_count=current_count,
                previous_week_count=previous_count,
                growth_pct=growth_pct,
                is_emerging=is_emerging,
                window_cost_exposure=cost,
            ))

        logger.info(
            "trend_detector_complete",
            clusters=len(results),
            emerging=sum(1 for r in results if r.is_emerging),
            cost_model="tiered" if has_labels else "flat",
            region_aware=has_regions,
        )
        return results

    # ── Cost computation ───────────────────────────────────────────────────

    def _compute_cost(
        self,
        group: pd.DataFrame,
        is_emerging: bool,
        has_labels: bool,
        has_regions: bool,
    ) -> float:
        if not has_labels:
            # Legacy: flat rate × cluster size
            return float(len(group)) * self._legacy_flat_cost

        total = 0.0
        for _, row in group.iterrows():
            label  = row.get("sentiment_label") if has_labels  else None
            region = row.get("region")          if has_regions else None

            mult = SENTIMENT_COST_MULTIPLIERS.get(
                str(label).upper() if label is not None else "",
                _UNKNOWN_MULTIPLIER,
            )
            total += base_cost_usd(region) * mult

        if is_emerging:
            total *= EMERGING_CLUSTER_COST_PENALTY

        return total

    # ── Growth math ────────────────────────────────────────────────────────

    @staticmethod
    def _wow_growth_pct(current: int, previous: int) -> float:
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return (current - previous) / previous * 100.0

    def _wow_growth(self, weekly_counts: pd.Series) -> float:
        if len(weekly_counts) < 2:
            return 0.0
        return self._wow_growth_pct(int(weekly_counts.iloc[-1]), int(weekly_counts.iloc[-2]))
