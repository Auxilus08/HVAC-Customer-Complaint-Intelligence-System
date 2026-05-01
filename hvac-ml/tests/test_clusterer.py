"""Tests for Clusterer — output types, fingerprints, silhouette, determinism."""

from __future__ import annotations

import numpy as np
import pytest

from pipeline.clusterer import ClusterResult, Clusterer


def _make_clustered_embeddings(
    n_clusters: int = 4,
    n_per_cluster: int = 30,
    dim: int = 384,
    seed: int = 42,
) -> np.ndarray:
    """Build embeddings with clear cluster structure for deterministic tests."""
    rng = np.random.default_rng(seed)
    parts: list[np.ndarray] = []
    for _ in range(n_clusters):
        center = rng.standard_normal(dim) * 6.0
        members = center + rng.standard_normal((n_per_cluster, dim)) * 0.05
        parts.append(members.astype(np.float32))
    return np.vstack(parts)


@pytest.fixture(scope="module")
def fitted_result() -> ClusterResult:
    embeddings = _make_clustered_embeddings()
    return Clusterer(hdbscan_min_cluster_size=10, random_state=42).fit(embeddings)


class TestClusterResultTypes:
    def test_output_types(self, fitted_result: ClusterResult) -> None:
        assert isinstance(fitted_result.labels, np.ndarray)
        assert isinstance(fitted_result.embeddings_50d, np.ndarray)
        assert isinstance(fitted_result.coords_2d, np.ndarray)
        assert isinstance(fitted_result.n_clusters, int)
        assert isinstance(fitted_result.noise_count, int)
        assert isinstance(fitted_result.noise_pct, float)
        assert isinstance(fitted_result.silhouette_score, float)
        assert isinstance(fitted_result.fingerprints, dict)
        assert isinstance(fitted_result.cluster_sizes, dict)


class TestClusterShapes:
    def test_50d_shape(self, fitted_result: ClusterResult) -> None:
        assert fitted_result.embeddings_50d.shape == (
            len(fitted_result.labels),
            50,
        )

    def test_2d_shape(self, fitted_result: ClusterResult) -> None:
        assert fitted_result.coords_2d.shape == (
            len(fitted_result.labels),
            2,
        )

    def test_labels_shape(self, fitted_result: ClusterResult) -> None:
        # 4 clusters of 30 members each
        assert fitted_result.labels.shape == (120,)


class TestClusterBehaviour:
    def test_finds_at_least_one_cluster(self, fitted_result: ClusterResult) -> None:
        assert fitted_result.n_clusters >= 1

    def test_min_cluster_size_respected(self, fitted_result: ClusterResult) -> None:
        for cid, size in fitted_result.cluster_sizes.items():
            assert size >= 10, f"cluster {cid} below min size: {size}"

    def test_noise_label_present_or_zero(self, fitted_result: ClusterResult) -> None:
        # Real-world data always produces at least some noise; with the synthetic
        # "ideal" clusters here we just assert noise_count is reported and labels
        # only contain valid IDs.
        valid_labels = set(fitted_result.cluster_sizes.keys()) | {-1}
        assert set(fitted_result.labels.tolist()).issubset(valid_labels)
        assert fitted_result.noise_count >= 0

    def test_noise_label_convention(self, fitted_result: ClusterResult) -> None:
        """All labels must be either -1 (noise) or a valid cluster id."""
        valid = set(fitted_result.cluster_sizes.keys()) | {-1}
        assert set(fitted_result.labels.tolist()).issubset(valid)

    def test_silhouette_range(self, fitted_result: ClusterResult) -> None:
        assert 0.0 < fitted_result.silhouette_score < 1.0


class TestFingerprints:
    def test_fingerprint_per_cluster(self, fitted_result: ClusterResult) -> None:
        assert set(fitted_result.fingerprints.keys()) == set(
            fitted_result.cluster_sizes.keys()
        )
        for fp in fitted_result.fingerprints.values():
            assert isinstance(fp, str) and len(fp) == 64

    def test_fingerprint_deterministic(self) -> None:
        embeddings = _make_clustered_embeddings()
        r1 = Clusterer(hdbscan_min_cluster_size=10, random_state=42).fit(embeddings)
        r2 = Clusterer(hdbscan_min_cluster_size=10, random_state=42).fit(embeddings)
        assert r1.fingerprints == r2.fingerprints


class TestDeterminism:
    def test_random_state_reproducibility(self) -> None:
        embeddings = _make_clustered_embeddings()
        r1 = Clusterer(hdbscan_min_cluster_size=10, random_state=42).fit(embeddings)
        r2 = Clusterer(hdbscan_min_cluster_size=10, random_state=42).fit(embeddings)
        np.testing.assert_array_equal(r1.labels, r2.labels)


class TestInputValidation:
    def test_invalid_input_raises(self) -> None:
        with pytest.raises(ValueError):
            Clusterer().fit(np.array([1.0, 2.0, 3.0]))
