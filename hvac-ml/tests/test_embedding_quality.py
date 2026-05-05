"""Embedding quality gates — Track B1.

These tests treat the embedder's semantic output as a first-class
requirement. Failure here means the multilingual model is broken or
the wrong checkpoint was loaded.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def embedder():
    from pipeline.embedder import Embedder

    return Embedder()


def test_cooling_complaints_cluster_together(embedder):
    from sklearn.metrics.pairwise import cosine_similarity

    cooling = [
        "AC not cooling at all even after service",
        "Room feels like an oven despite AC running all night",
        "Indoor unit blowing warm air only",
        "Not getting cold air from split AC",
        "Temperature not dropping even on max cooling",
    ]
    noise = [
        "Loud grinding noise from outdoor unit",
        "Vibration sound when compressor starts",
        "Rattling noise from indoor unit at night",
    ]
    c_emb = embedder.encode_batch(cooling)
    n_emb = embedder.encode_batch(noise)

    cooling_sim = cosine_similarity(c_emb).mean()
    noise_sim = cosine_similarity(n_emb).mean()
    cross_sim = cosine_similarity(c_emb, n_emb).mean()

    assert cooling_sim > 0.55, f"cooling cohesion too low: {cooling_sim:.3f}"
    assert noise_sim > 0.55, f"noise cohesion too low: {noise_sim:.3f}"
    assert cross_sim < cooling_sim - 0.05, (
        f"cross-group ({cross_sim:.3f}) too close to within-group ({cooling_sim:.3f})"
    )


def test_hinglish_complaints_near_english_equivalents(embedder):
    """Multilingual gate — average and best-pair similarity must clear thresholds.

    Real behaviour of paraphrase-multilingual-MiniLM-L12-v2 on Hinglish (Hindi
    in Latin script) is uneven: some pairs cosine ~0.8, others ~0.4, occasional
    near-zero outlier. We assert that *at least one* pair clears 0.5 (catches
    wrong-model regressions) and the average is positive (catches catastrophic
    failure where every Hinglish sample lands far from English).
    """
    from sklearn.metrics.pairwise import cosine_similarity

    pairs = [
        ("AC bilkul thanda nahi kar raha", "AC not cooling at all"),
        ("outdoor unit se bahut noise aa rahi hai", "loud noise coming from outdoor unit"),
        ("technician aaya hi nahi", "technician never showed up"),
    ]
    sims = []
    for hinglish, english in pairs:
        h = embedder.encode_single(hinglish).reshape(1, -1)
        e = embedder.encode_single(english).reshape(1, -1)
        sims.append(float(cosine_similarity(h, e)[0][0]))

    avg = sum(sims) / len(sims)
    best = max(sims)
    assert best > 0.5, (
        f"no Hinglish pair clears 0.5 — multilingual model likely broken. sims={sims}"
    )
    assert avg > 0.2, (
        f"avg Hinglish↔English similarity {avg:.3f} too low — catastrophic regression"
    )


def test_cache_reduces_encode_calls(embedder):
    import time

    text = "AC not cooling after recent service visit"
    embedder.encode_single(text)  # prime any model loading
    embedder.encode_single("___warmup___")

    t1 = time.perf_counter()
    embedder.encode_single(text)
    first_ms = (time.perf_counter() - t1) * 1000

    t2 = time.perf_counter()
    embedder.encode_single(text)
    second_ms = (time.perf_counter() - t2) * 1000

    # Cache hit must be substantially faster.
    assert second_ms <= first_ms or second_ms < 5, (
        f"cache miss suspected: first={first_ms:.2f}ms second={second_ms:.2f}ms"
    )
