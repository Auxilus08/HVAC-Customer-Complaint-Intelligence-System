"""Clustering quality gates — Track B2.

Runs the full pipeline on a fixed synthetic distribution and asserts
that silhouette / noise / size distribution stay inside production
quality bounds. Marked slow — excluded from fast CI runs.
"""

from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.slow

SEED = 42


def _synthetic_complaints(n: int = 500) -> list[str]:
    """Build a synthetic distribution mirroring the real corpus shape."""
    templates = {
        "cooling": [
            "AC not cooling at all",
            "Room feels warm despite AC on max",
            "Indoor unit blowing warm air only",
            "Temperature not dropping",
            "Cooling efficiency very poor since service",
        ],
        "noise": [
            "Loud grinding noise from outdoor unit",
            "Compressor making rattling noise",
            "Indoor unit fan vibrating",
            "Strange humming from condenser",
            "Outdoor unit very noisy at night",
        ],
        "leak": [
            "Water leaking from indoor unit",
            "Refrigerant hissing sound from copper line",
            "Drain pipe leaking water",
            "Wall stained from AC water leak",
            "Continuous dripping from indoor unit",
        ],
        "electrical": [
            "AC trips MCB on startup",
            "Breaker pops every time AC turns on",
            "Power supply issue when compressor starts",
            "Sparks from outdoor unit power line",
            "AC shutting off due to electrical fault",
        ],
        "service": [
            "Technician never came on scheduled date",
            "Service request pending for two weeks",
            "Field engineer rude and unhelpful",
            "Charged twice for same service visit",
            "Installation done improperly",
        ],
    }
    rng = np.random.default_rng(SEED)
    items: list[str] = []
    keys = list(templates.keys())
    for _ in range(n):
        cat = rng.choice(keys)
        base = rng.choice(templates[cat])
        items.append(str(base))
    return items


@pytest.fixture(scope="module")
def pipeline_output():
    from pipeline.clusterer import Clusterer
    from pipeline.embedder import Embedder

    texts = _synthetic_complaints(500)
    embeddings = Embedder().encode_batch(texts)
    ids = list(range(len(texts)))
    result = Clusterer(random_state=SEED).fit(embeddings, ids=ids)
    return texts, embeddings, result


def test_minimum_cluster_count(pipeline_output):
    _, _, result = pipeline_output
    assert result.n_clusters >= 3, (
        f"only {result.n_clusters} clusters discovered — expected >= 3"
    )


def test_silhouette_score_gate(pipeline_output):
    """Most important ML quality gate: silhouette must clear 0.2."""
    _, _, result = pipeline_output
    sil = result.silhouette_score
    assert sil is not None, "silhouette_score not computed"
    assert sil > 0.2, f"silhouette {sil:.3f} below 0.2 — cluster quality unacceptable"


def test_noise_rate_acceptable(pipeline_output):
    _, _, result = pipeline_output
    assert result.noise_pct < 30.0, (
        f"noise rate {result.noise_pct:.1f}% above 30% threshold"
    )


def test_cluster_size_distribution(pipeline_output):
    """No single cluster may swallow >50% of complaints."""
    _, _, result = pipeline_output
    sizes = {k: v for k, v in result.cluster_sizes.items() if k != -1}
    if not sizes:
        pytest.fail("no non-noise clusters")
    biggest = max(sizes.values())
    assert biggest < 250, f"dominant cluster too large: {biggest} complaints"


def test_fingerprints_deterministic(pipeline_output):
    """Same data + seed => identical fingerprints."""
    from pipeline.clusterer import Clusterer

    _, embeddings, result1 = pipeline_output
    ids = list(range(len(embeddings)))
    result2 = Clusterer(random_state=SEED).fit(embeddings, ids=ids)
    assert result1.fingerprints == result2.fingerprints, (
        "fingerprints non-deterministic — random_state not honored"
    )
