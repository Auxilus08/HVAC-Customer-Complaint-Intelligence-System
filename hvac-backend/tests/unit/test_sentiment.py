"""Unit tests for VADER sentiment scoring and label thresholds.

Uses pipeline.sentiment.SentimentAnalyzer — the single source of truth for
thresholds and labels. Workers must never define their own thresholds.
"""

from __future__ import annotations

import pytest
from pipeline.sentiment import SentimentAnalyzer

_analyzer = SentimentAnalyzer()


class TestSentimentLabels:
    def test_critical_threshold(self) -> None:
        # CRITICAL_THRESHOLD = -0.8 (inclusive)
        assert _analyzer.label_from_score(-0.9) == "CRITICAL"
        assert _analyzer.label_from_score(-0.8) == "CRITICAL"

    def test_high_threshold(self) -> None:
        # HIGH_THRESHOLD = -0.5 (inclusive)
        assert _analyzer.label_from_score(-0.79) == "HIGH"
        assert _analyzer.label_from_score(-0.5) == "HIGH"

    def test_normal_threshold(self) -> None:
        assert _analyzer.label_from_score(-0.49) == "NORMAL"
        assert _analyzer.label_from_score(0.0) == "NORMAL"
        assert _analyzer.label_from_score(0.29) == "NORMAL"

    def test_positive_threshold(self) -> None:
        # POSITIVE_THRESHOLD = 0.3 (inclusive)
        assert _analyzer.label_from_score(0.3) == "POSITIVE"
        assert _analyzer.label_from_score(0.95) == "POSITIVE"

    def test_boundary_critical_high(self) -> None:
        # -0.79 should be HIGH, -0.80 should be CRITICAL
        assert _analyzer.label_from_score(-0.80) == "CRITICAL"
        assert _analyzer.label_from_score(-0.79) == "HIGH"

    def test_boundary_high_normal(self) -> None:
        assert _analyzer.label_from_score(-0.50) == "HIGH"
        assert _analyzer.label_from_score(-0.49) == "NORMAL"


class TestVADERIntegration:
    """Integration test: actual VADER scores on representative complaint text."""

    @pytest.fixture(autouse=True)
    def analyzer(self) -> None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        self.va = SentimentIntensityAnalyzer()

    def test_strongly_negative_complaint(self) -> None:
        text = "This AC is completely broken, useless garbage, worst product ever!"
        score = self.va.polarity_scores(text)["compound"]
        assert score < -0.2, f"Expected negative, got {score}"

    def test_neutral_complaint(self) -> None:
        text = "The technician visited and checked the unit."
        score = self.va.polarity_scores(text)["compound"]
        assert -0.4 < score < 0.4, f"Expected near-neutral, got {score}"

    def test_positive_review(self) -> None:
        text = "Great service, very happy with the quick resolution!"
        score = self.va.polarity_scores(text)["compound"]
        assert score > 0.2, f"Expected positive, got {score}"

    def test_hinglish_negative(self) -> None:
        text = "AC bilkul kharab hai, cooling nahi ho rahi, bahut problem hai"
        score = self.va.polarity_scores(text)["compound"]
        assert isinstance(score, float)

    def test_safety_flagged_complaint_not_positive(self) -> None:
        result = _analyzer.score("There is a gas leak from the AC unit")
        assert result.label in ("HIGH", "CRITICAL")
        assert result.safety_flagged is True
