"""VADER sentiment scoring with HVAC-tuned thresholds.

This is the SINGLE source of truth for sentiment thresholds. hvac-backend
workers MUST import SentimentAnalyzer from here — never instantiate VADER
directly. Changing a threshold here changes it everywhere.

Thresholds are exposed as class-level constants so they can be tuned in one
place and read from anywhere (alerts, dashboards, tests).

HVAC safety override
--------------------
VADER's general-purpose lexicon misreads HVAC safety phrasings: "gas leak",
"refrigerant leak", "hissing sound", "burning smell" all score neutral or
even positive because words like "strong" carry positive valence in the
default lexicon. SAFETY_OVERRIDE_LEXICON bumps these terms strongly negative
and FLOOR_LABEL_FOR_SAFETY clamps any safety-mention complaint to at minimum
HIGH severity, regardless of compound score. This prevents the worst class
of failure: silently down-ranking a gas leak as POSITIVE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = structlog.get_logger(__name__)

# ── HVAC domain safety lexicon — added to VADER on init ──────────────────
# VADER scale: -4 (most negative) … +4 (most positive). We push these terms
# to -3.5 so any single mention drives compound deeply negative.
SAFETY_OVERRIDE_LEXICON: dict[str, float] = {
    "smoke": -3.0,
    "spark": -2.5,
    "shock": -3.0,
    "explosion": -3.8,
    "leak": -2.0,
    "leaking": -2.0,
    "leakage": -2.0,
    "hissing": -2.5,
    "trips": -2.0,
    "tripping": -2.0,
    "tripped": -2.0,
    "broken": -2.5,
    "defective": -2.5,
    "faulty": -2.5,
    "damaged": -2.0,
    "ruined": -3.0,
    "useless": -3.0,
    "pathetic": -3.0,
    "shoddy": -2.5,
    "fixed": 3.2,            # positive so VADER's "not fixed" negation fires
    "unresolved": -2.0,
    "unfixed": -2.0,
    "unattended": -2.0,
    "ghatiya": -3.0,         # Hinglish: terrible / pathetic
    "bekaar": -3.0,          # Hinglish: useless
    "kharab": -2.5,          # Hinglish: damaged / spoilt
    "pareshan": -2.0,        # Hinglish: troubled
    "takleef": -2.5,         # Hinglish: suffering / discomfort
    "barbaad": -3.0,         # Hinglish: ruined
}

# Words that, if present, force at least HIGH severity even when VADER reads
# the surrounding text as positive — guards against the "strong hissing"
# blind spot where VADER reads "strong" as +.
_SAFETY_FLOOR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(gas leak|refrigerant leak|gas leakage)\b", re.IGNORECASE),
    re.compile(r"\b(fire hazard|burning smell|smoke|spark|explosion)\b", re.IGNORECASE),
    re.compile(r"\b(electrical shock|electric shock)\b", re.IGNORECASE),
    re.compile(r"\bhissing\b.*\b(smell|gas|refrigerant)\b", re.IGNORECASE),
    re.compile(r"\b(smell|odour|odor).*\b(gas|chemical|refrigerant|burning)\b", re.IGNORECASE),
]


# Single-word safety tokens that should also trigger the floor, even without
# a multi-word regex match (e.g. "leak" alone, not just "gas leak").
_SAFETY_FLOOR_WORDS: frozenset[str] = frozenset(
    k for k, v in SAFETY_OVERRIDE_LEXICON.items() if v <= -2.5
)


def _is_safety_critical(text: str) -> bool:
    """True when the text mentions any safety-critical scenario.

    Checks both multi-word regex patterns AND standalone safety keywords
    from the lexicon (score ≤ -2.5) so the floor stays aligned with the
    lexicon entries.
    """
    if any(p.search(text) for p in _SAFETY_FLOOR_PATTERNS):
        return True
    text_lower = text.lower()
    return any(
        f" {w} " in f" {text_lower} "
        for w in _SAFETY_FLOOR_WORDS
    )


@dataclass
class SentimentResult:
    compound: float
    label: str  # CRITICAL | HIGH | NORMAL | POSITIVE
    positive: float
    negative: float
    neutral: float
    safety_flagged: bool = False  # True when a safety pattern matched


class SentimentAnalyzer:
    """VADER-based sentiment scoring with an HVAC safety lexicon override.

    Label rules (compound score):
        compound <= CRITICAL_THRESHOLD → CRITICAL
        compound <= HIGH_THRESHOLD     → HIGH
        compound >= POSITIVE_THRESHOLD → POSITIVE
        else                           → NORMAL

    Safety override: any text matching a safety pattern is forced to at least
    HIGH, never POSITIVE — even if VADER's compound score reads positive.
    """

    CRITICAL_THRESHOLD: float = -0.8
    HIGH_THRESHOLD: float = -0.5
    POSITIVE_THRESHOLD: float = 0.3

    def __init__(self) -> None:
        self._analyzer = SentimentIntensityAnalyzer()
        # Inject HVAC safety lexicon — VADER lower-cases keys at lookup,
        # so we store them lower-case here.
        self._analyzer.lexicon.update(
            {k.lower(): v for k, v in SAFETY_OVERRIDE_LEXICON.items()}
        )

    def label_from_score(self, compound: float) -> str:
        """Map a VADER compound score to its severity label.

        Boundaries are inclusive on the negative side per the spec:
            -0.8  → CRITICAL
            -0.5  → HIGH
        """
        if compound <= self.CRITICAL_THRESHOLD:
            return "CRITICAL"
        if compound <= self.HIGH_THRESHOLD:
            return "HIGH"
        if compound >= self.POSITIVE_THRESHOLD:
            return "POSITIVE"
        return "NORMAL"

    def score(self, text: str) -> SentimentResult:
        """Score a single complaint, returning a SentimentResult.

        Safety-flagged complaints can never end up labelled POSITIVE — they
        are clamped to a HIGH or CRITICAL label according to compound score.
        """
        scores = self._analyzer.polarity_scores(text)
        compound = float(scores["compound"])
        label = self.label_from_score(compound)
        flagged = _is_safety_critical(text)
        if flagged and label in ("POSITIVE", "NORMAL"):
            # Safety floor: minimum HIGH for any safety-critical complaint.
            label = "HIGH"
            compound = min(compound, self.HIGH_THRESHOLD - 0.01)

        return SentimentResult(
            compound=compound,
            label=label,
            positive=float(scores["pos"]),
            negative=float(scores["neg"]),
            neutral=float(scores["neu"]),
            safety_flagged=flagged,
        )

    def score_batch(self, texts: list[str]) -> list[SentimentResult]:
        """Score multiple complaints, preserving input order."""
        return [self.score(t) for t in texts]
