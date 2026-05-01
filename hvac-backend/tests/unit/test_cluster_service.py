"""Unit tests for cluster priority score calculation."""

from __future__ import annotations

from app.services.cluster_service import compute_priority_score


class TestPriorityScore:
    def test_all_zeros(self) -> None:
        score = compute_priority_score(
            avg_sentiment=0.0, growth_pct_wow=0.0, member_count=0
        )
        assert 0.0 <= score <= 1.0

    def test_worst_case_returns_high_score(self) -> None:
        score = compute_priority_score(
            avg_sentiment=-1.0,
            growth_pct_wow=2.0,
            member_count=500,
            max_member_count=500,
        )
        assert score > 0.8

    def test_positive_sentiment_gives_low_score(self) -> None:
        score = compute_priority_score(
            avg_sentiment=0.9,
            growth_pct_wow=0.0,
            member_count=5,
            max_member_count=500,
        )
        assert score < 0.2

    def test_score_bounded_between_0_and_1(self) -> None:
        for sentiment in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            for growth in [-0.5, 0.0, 0.5, 2.0, 5.0]:
                score = compute_priority_score(
                    avg_sentiment=sentiment,
                    growth_pct_wow=growth,
                    member_count=100,
                    max_member_count=1000,
                )
                assert (
                    0.0 <= score <= 1.0
                ), f"score={score} out of bounds for sentiment={sentiment}, growth={growth}"

    def test_none_values_handled(self) -> None:
        score = compute_priority_score(
            avg_sentiment=None, growth_pct_wow=None, member_count=None
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_high_growth_increases_score(self) -> None:
        low_growth = compute_priority_score(
            avg_sentiment=-0.3,
            growth_pct_wow=0.1,
            member_count=50,
            max_member_count=100,
        )
        high_growth = compute_priority_score(
            avg_sentiment=-0.3,
            growth_pct_wow=1.5,
            member_count=50,
            max_member_count=100,
        )
        assert high_growth > low_growth
