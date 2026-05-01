"""Tests for SentimentAnalyzer — thresholds, labels, batch behaviour."""

from __future__ import annotations

import pytest

from pipeline.sentiment import SentimentAnalyzer, SentimentResult


@pytest.fixture(scope="module")
def analyzer() -> SentimentAnalyzer:
    return SentimentAnalyzer()


class TestLabelFromScore:
    def test_critical_below_threshold(self, analyzer: SentimentAnalyzer) -> None:
        assert analyzer.label_from_score(-0.95) == "CRITICAL"
        assert analyzer.label_from_score(-0.81) == "CRITICAL"

    def test_high_band(self, analyzer: SentimentAnalyzer) -> None:
        assert analyzer.label_from_score(-0.79) == "HIGH"
        assert analyzer.label_from_score(-0.51) == "HIGH"

    def test_normal_band(self, analyzer: SentimentAnalyzer) -> None:
        assert analyzer.label_from_score(-0.49) == "NORMAL"
        assert analyzer.label_from_score(0.0) == "NORMAL"
        assert analyzer.label_from_score(0.29) == "NORMAL"

    def test_positive_band(self, analyzer: SentimentAnalyzer) -> None:
        assert analyzer.label_from_score(0.3) == "POSITIVE"
        assert analyzer.label_from_score(0.95) == "POSITIVE"

    def test_threshold_boundary_high(self, analyzer: SentimentAnalyzer) -> None:
        # exactly -0.5 → HIGH (inclusive on negative side)
        assert analyzer.label_from_score(-0.5) == "HIGH"

    def test_threshold_boundary_critical(self, analyzer: SentimentAnalyzer) -> None:
        # exactly -0.8 → CRITICAL (inclusive)
        assert analyzer.label_from_score(-0.8) == "CRITICAL"


class TestScoring:
    def test_angry_is_critical(self, analyzer: SentimentAnalyzer) -> None:
        result = analyzer.score("TERRIBLE PRODUCT!!! WORST COMPANY EVER!!!")
        assert result.label == "CRITICAL", (
            f"got {result.label} compound={result.compound:.3f}"
        )

    def test_negative_is_high(self, analyzer: SentimentAnalyzer) -> None:
        result = analyzer.score(
            "Technician came three times and still not fixed"
        )
        assert result.label == "HIGH", (
            f"got {result.label} compound={result.compound:.3f}"
        )

    def test_strongly_negative_is_high(self, analyzer: SentimentAnalyzer) -> None:
        result = analyzer.score(
            "Service is bad, technician never came, very angry and disappointed"
        )
        assert result.label == "HIGH"

    def test_neutral_is_normal(self, analyzer: SentimentAnalyzer) -> None:
        result = analyzer.score("AC not cooling, please check and confirm")
        assert result.label == "NORMAL"

    def test_positive_text(self, analyzer: SentimentAnalyzer) -> None:
        result = analyzer.score(
            "Excellent service, fixed same day, very happy and satisfied"
        )
        assert result.label == "POSITIVE"

    def test_score_returns_sentiment_result(self, analyzer: SentimentAnalyzer) -> None:
        result = analyzer.score("any text")
        assert isinstance(result, SentimentResult)
        assert -1.0 <= result.compound <= 1.0
        assert abs(result.positive + result.negative + result.neutral - 1.0) < 1e-3


class TestBatch:
    def test_batch_length(self, analyzer: SentimentAnalyzer) -> None:
        texts = [f"complaint {i}" for i in range(10)]
        results = analyzer.score_batch(texts)
        assert len(results) == 10

    def test_batch_order_preserved(self, analyzer: SentimentAnalyzer) -> None:
        results = analyzer.score_batch(
            ["This is awful and broken", "Great wonderful happy service"]
        )
        assert results[0].compound < results[1].compound


class TestConstants:
    def test_thresholds_are_class_constants(self) -> None:
        assert SentimentAnalyzer.CRITICAL_THRESHOLD == -0.8
        assert SentimentAnalyzer.HIGH_THRESHOLD == -0.5
        assert SentimentAnalyzer.POSITIVE_THRESHOLD == 0.3
