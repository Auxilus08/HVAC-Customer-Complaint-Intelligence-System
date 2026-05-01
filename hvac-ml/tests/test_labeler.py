"""Tests for ClusterLabeler — Jaccard logic, gating, mocked Gemini calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pipeline.labeler import ClusterLabeler


@pytest.fixture
def labeler() -> ClusterLabeler:
    # api_key="test" avoids env-var dependency; we never make a real call.
    return ClusterLabeler(api_key="test", jaccard_threshold=0.2)


class TestJaccardDistance:
    def test_jaccard_identical(self, labeler: ClusterLabeler) -> None:
        assert labeler.jaccard_distance({1, 2, 3}, {1, 2, 3}) == 0.0

    def test_jaccard_disjoint(self, labeler: ClusterLabeler) -> None:
        assert labeler.jaccard_distance({1, 2, 3}, {4, 5, 6}) == 1.0

    def test_jaccard_partial(self, labeler: ClusterLabeler) -> None:
        # {1,2,3} ∩ {2,3,4} = {2,3}, union = {1,2,3,4} → 2/4 = 0.5
        assert labeler.jaccard_distance({1, 2, 3}, {2, 3, 4}) == 0.5

    def test_jaccard_empty_pair(self, labeler: ClusterLabeler) -> None:
        assert labeler.jaccard_distance(set(), set()) == 0.0


class TestShouldRelabel:
    def test_below_threshold_skips(self, labeler: ClusterLabeler) -> None:
        # |∩|=9, |∪|=10 → distance = 0.1 < 0.2
        a = {1, 2, 3, 4, 5, 6, 7, 8, 9}
        b = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
        assert labeler.jaccard_distance(a, b) < 0.2
        assert labeler.should_relabel(a, b) is False

    def test_above_threshold_relabels(self, labeler: ClusterLabeler) -> None:
        # Distance = 0.5 > 0.2
        assert labeler.should_relabel({1, 2, 3}, {2, 3, 4}) is True

    def test_at_threshold_does_not_relabel(self, labeler: ClusterLabeler) -> None:
        """The gate uses strict inequality — exactly at threshold means skip."""
        a = {1, 2, 3, 4, 5, 6, 7, 8}
        b = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
        # |∩|=8, |∪|=10 → distance = 0.2
        assert labeler.jaccard_distance(a, b) == pytest.approx(0.2)
        assert labeler.should_relabel(a, b) is False


class TestLabelCluster:
    def test_label_cluster_returns_string(self, labeler: ClusterLabeler) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "Compressor Noise Outdoor Unit"
        with patch.object(
            labeler._client, "generate_content", return_value=mock_resp
        ) as spy:
            label = labeler.label_cluster(
                ["loud grinding noise", "rattling sound", "humming compressor"]
            )
            spy.assert_called_once()
            assert isinstance(label, str)
            words = label.split()
            assert 2 <= len(words) <= 6, f"label '{label}' word count off"

    def test_label_cluster_pii_stripped(self, labeler: ClusterLabeler) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "Service Delay Issue"
        complaint_with_pii = (
            "Call me back on +91 9876543210 or email user@example.com"
        )
        with patch.object(
            labeler._client, "generate_content", return_value=mock_resp
        ) as spy:
            labeler.label_cluster([complaint_with_pii])
            sent_text = spy.call_args.args[0]
            assert "9876543210" not in sent_text
            assert "user@example.com" not in sent_text
            assert "[REDACTED]" in sent_text


class TestLabelAllClusters:
    def test_skips_unchanged_clusters(self, labeler: ClusterLabeler) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "New Label"
        with patch.object(
            labeler._client, "generate_content", return_value=mock_resp
        ) as spy:
            labels = labeler.label_all_clusters(
                cluster_complaints={
                    0: ["unchanged cluster sample"],
                    1: ["completely different sample"],
                },
                old_fingerprints={0: {1, 2, 3, 4, 5}, 1: {10, 11, 12}},
                new_fingerprints={0: {1, 2, 3, 4, 5}, 1: {20, 21, 22}},
                previous_labels={0: "Existing Label", 1: "Stale Label"},
            )
            # cluster 0 unchanged → reused; cluster 1 disjoint → relabeled
            assert labels[0] == "Existing Label"
            assert labels[1] == "New Label"
            assert spy.call_count == 1

    def test_no_history_labels_all(self, labeler: ClusterLabeler) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "Fresh Label"
        with patch.object(
            labeler._client, "generate_content", return_value=mock_resp
        ) as spy:
            labels = labeler.label_all_clusters(
                cluster_complaints={0: ["x"], 1: ["y"], 2: ["z"]}
            )
            assert spy.call_count == 3
            assert set(labels.keys()) == {0, 1, 2}

    def test_label_all_returns_for_every_cluster(
        self, labeler: ClusterLabeler
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "Some Label"
        with patch.object(
            labeler._client, "generate_content", return_value=mock_resp
        ):
            labels = labeler.label_all_clusters({0: ["a"], 1: ["b"]})
            assert len(labels) == 2
