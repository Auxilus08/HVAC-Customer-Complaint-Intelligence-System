"""UMAP (50D for clustering + 2D for visualisation) + HDBSCAN.

Single source of truth for HVAC complaint clustering. The hvac-backend
worker imports this class — it never reimplements UMAP or HDBSCAN.

Design rules:
  - Two independent UMAP fits: 50D for HDBSCAN, 2D for the scatter plot only.
  - HDBSCAN is NEVER run on 2D coords.
  - Each cluster gets a SHA-256 fingerprint over its sorted member indices,
    used downstream by the labeler to decide whether a relabel is needed.
  - Silhouette score is computed on 50D embeddings, excluding noise.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import hdbscan  # type: ignore[import]
import numpy as np
import structlog
import umap  # type: ignore[import]
from sklearn.metrics import silhouette_score as sk_silhouette

logger = structlog.get_logger(__name__)


@dataclass
class ClusterResult:
    """Output of the full UMAP + HDBSCAN pipeline."""

    labels: np.ndarray              # shape (N,) int — -1 for noise
    embeddings_50d: np.ndarray      # shape (N, 50) — input to HDBSCAN
    coords_2d: np.ndarray           # shape (N, 2) — for scatter plot only
    n_clusters: int                 # excluding noise
    noise_count: int
    noise_pct: float                # 0.0 – 100.0
    silhouette_score: float         # NaN if only 1 cluster
    fingerprints: dict[int, str]    # cluster_id → SHA-256 of sorted indices
    cluster_sizes: dict[int, int]   # cluster_id → member count
    probabilities: np.ndarray = field(default_factory=lambda: np.zeros(0))


class Clusterer:
    """UMAP (50D + 2D) + HDBSCAN, with cluster fingerprints and silhouette.

    Args:
        umap_n_components_cluster: UMAP target dim for clustering.
        umap_n_components_viz:     UMAP target dim for the scatter plot.
        hdbscan_min_cluster_size:  Smallest acceptable cluster.
        metric:                    Distance metric for UMAP.
        random_state:              Seed for reproducibility.
    """

    def __init__(
        self,
        umap_n_components_cluster: int = 50,
        umap_n_components_viz: int = 2,
        hdbscan_min_cluster_size: int = 15,
        metric: str = "cosine",
        random_state: int = 42,
        umap_n_neighbors: int = 15,
    ) -> None:
        self.umap_n_components_cluster = umap_n_components_cluster
        self.umap_n_components_viz = umap_n_components_viz
        self.hdbscan_min_cluster_size = hdbscan_min_cluster_size
        self.metric = metric
        self.random_state = random_state
        self.umap_n_neighbors = umap_n_neighbors

    # ── Pipeline ───────────────────────────────────────────────────────────
    def fit(
        self,
        embeddings: np.ndarray,
        ids: np.ndarray | list[int] | None = None,
    ) -> ClusterResult:
        """Run the full UMAP → HDBSCAN pipeline on *embeddings* (N, D)."""
        if embeddings.ndim != 2:
            raise ValueError(
                f"Expected 2D array (N, D), got shape {embeddings.shape}"
            )
        n = len(embeddings)

        id_array = (
            np.asarray(ids, dtype=np.int64)
            if ids is not None
            else np.arange(len(embeddings), dtype=np.int64)
        )
        if len(id_array) != len(embeddings):
            raise ValueError(
                f"ids length ({len(id_array)}) must match "
                f"embeddings length ({len(embeddings)})"
            )

        # 1. UMAP 384D → 50D for clustering ─────────────────────────────────
        reducer_50d = umap.UMAP(
            n_components=self.umap_n_components_cluster,
            metric=self.metric,
            random_state=self.random_state,
            n_neighbors=self.umap_n_neighbors,
            min_dist=0.0,
        )
        embeddings_50d = np.asarray(reducer_50d.fit_transform(embeddings))

        # 2. HDBSCAN on the 50D embeddings ───────────────────────────────────
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.hdbscan_min_cluster_size,
            metric="euclidean",
            prediction_data=True,
        )
        labels = clusterer.fit_predict(embeddings_50d).astype(np.int64)
        probabilities = clusterer.probabilities_

        # 3. UMAP 384D → 2D for visualisation only ───────────────────────────
        reducer_2d = umap.UMAP(
            n_components=self.umap_n_components_viz,
            metric=self.metric,
            random_state=self.random_state,
            n_neighbors=self.umap_n_neighbors,
            min_dist=0.1,
        )
        coords_2d = np.asarray(reducer_2d.fit_transform(embeddings))

        # 4. Cluster fingerprints + sizes ────────────────────────────────────
        unique_labels = sorted(int(l) for l in set(labels.tolist()) if l != -1)
        fingerprints = {
            cid: self._compute_fingerprint(labels, cid, id_array)
            for cid in unique_labels
        }
        cluster_sizes = {
            cid: int((labels == cid).sum()) for cid in unique_labels
        }

        # 5. Noise stats + silhouette ────────────────────────────────────────
        noise_count = int((labels == -1).sum())
        noise_pct = 100.0 * noise_count / n if n else 0.0
        silhouette = self._compute_silhouette(embeddings_50d, labels)

        logger.info(
            "clusterer_fit_complete",
            n=n,
            n_clusters=len(unique_labels),
            noise_count=noise_count,
            noise_pct=round(noise_pct, 2),
            silhouette=round(silhouette, 3) if not np.isnan(silhouette) else None,
        )

        return ClusterResult(
            labels=labels,
            embeddings_50d=embeddings_50d,
            coords_2d=coords_2d,
            n_clusters=len(unique_labels),
            noise_count=noise_count,
            noise_pct=noise_pct,
            silhouette_score=silhouette,
            fingerprints=fingerprints,
            cluster_sizes=cluster_sizes,
            probabilities=probabilities,
        )

    # ── Internal helpers ───────────────────────────────────────────────────
    def _compute_fingerprint(
        self, labels: np.ndarray, cluster_id: int, id_array: np.ndarray,
    ) -> str:
        """SHA-256 over the sorted complaint IDs belonging to *cluster_id*."""
        member_ids = id_array[labels == cluster_id].tolist()
        member_ids.sort()
        payload = ",".join(str(i) for i in member_ids)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _compute_silhouette(
        self, embeddings_50d: np.ndarray, labels: np.ndarray
    ) -> float:
        """Silhouette score on 50D, excluding noise (-1) labels.

        Returns NaN if fewer than 2 clusters survive after dropping noise.
        """
        mask = labels != -1
        if mask.sum() < 2:
            return float("nan")
        kept_labels = labels[mask]
        if len(set(kept_labels.tolist())) < 2:
            return float("nan")
        try:
            return float(
                sk_silhouette(
                    embeddings_50d[mask], kept_labels, metric="euclidean"
                )
            )
        except ValueError:
            return float("nan")
