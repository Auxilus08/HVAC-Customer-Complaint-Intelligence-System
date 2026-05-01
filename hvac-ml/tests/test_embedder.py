"""Tests for Embedder — shape, cache hit, semantic similarity, determinism."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from pipeline.embedder import EMBEDDING_DIM, Embedder


@pytest.fixture(scope="module")
def embedder() -> Embedder:
    return Embedder()


class TestEmbedderShape:
    def test_output_shape(self, embedder: Embedder) -> None:
        result = embedder.encode_single("AC not cooling")
        assert result.shape == (EMBEDDING_DIM,)
        assert result.dtype == np.float32

    def test_batch_shape(self, embedder: Embedder) -> None:
        texts = ["one complaint", "two complaint", "three complaint"]
        result = embedder.encode_batch(texts)
        assert result.shape == (3, EMBEDDING_DIM)

    def test_empty_batch(self, embedder: Embedder) -> None:
        result = embedder.encode_batch([])
        assert result.shape == (0, EMBEDDING_DIM)

    def test_l2_normalized(self, embedder: Embedder) -> None:
        vectors = embedder.encode_batch(["short text", "another sample"])
        norms = np.linalg.norm(vectors, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)


class TestEmbedderSemantics:
    def test_semantic_similarity(self, embedder: Embedder) -> None:
        # Tight paraphrase pair — must be clearly closer than an unrelated topic.
        a = embedder.encode_single("AC is not cooling at all")
        b = embedder.encode_single("AC unit is not cooling the room properly")
        cosine = float(np.dot(a, b))
        assert cosine > 0.6, f"expected > 0.6, got {cosine:.3f}"

    def test_semantic_difference(self, embedder: Embedder) -> None:
        a = embedder.encode_single("AC not cooling")
        b = embedder.encode_single("Grinding noise from outdoor unit")
        cosine = float(np.dot(a, b))
        assert cosine < 0.4, f"expected < 0.4, got {cosine:.3f}"

    def test_semantic_ordering(self, embedder: Embedder) -> None:
        """Same-topic pair must be more similar than cross-topic pair."""
        cooling_a = embedder.encode_single("AC not cooling at all")
        cooling_b = embedder.encode_single("Room feels like an oven, AC failing")
        noise = embedder.encode_single("Grinding noise from outdoor unit")
        sim_same = float(np.dot(cooling_a, cooling_b))
        sim_cross = float(np.dot(cooling_a, noise))
        assert sim_same > sim_cross, (
            f"cooling-pair {sim_same:.3f} should exceed cross {sim_cross:.3f}"
        )

    def test_deterministic(self, embedder: Embedder) -> None:
        text = "Compressor making loud grinding noise outdoor"
        v1 = embedder.encode_single(text)
        v2 = embedder.encode_single(text)
        np.testing.assert_array_equal(v1, v2)

    def test_case_variants_produce_independent_embeddings(
        self, embedder: Embedder
    ) -> None:
        upper = embedder.encode_single("TERRIBLE AC NOT WORKING AT ALL")
        lower = embedder.encode_single("terrible ac not working at all")
        cosine = float(np.dot(upper, lower))
        assert cosine > 0.85, "case variants should be semantically near-identical"
        assert not np.array_equal(upper, lower) or cosine == pytest.approx(
            1.0, abs=1e-5
        ), "both variants should have been independently encoded"

    def test_cache_key_is_case_sensitive(self, embedder: Embedder) -> None:
        h1 = embedder._text_hash("HELLO WORLD")
        h2 = embedder._text_hash("hello world")
        assert h1 != h2, "after Bug 1 fix, keys must differ for different cases"


class TestEmbedderCache:
    def test_cache_hit_skips_model(self, embedder: Embedder) -> None:
        text = "unique-cache-test-text-xyz-9876"
        embedder.encode_single(text)
        with patch.object(
            embedder._model, "encode", wraps=embedder._model.encode
        ) as spy:
            embedder.encode_single(text)
            assert spy.call_count == 0

    def test_batch_cache_hit_only_uncached_called(self, embedder: Embedder) -> None:
        seen_text = "previously-seen-text-abc-123"
        new_text = "freshly-new-text-batch-test-7"
        embedder.encode_single(seen_text)
        with patch.object(
            embedder._model, "encode", wraps=embedder._model.encode
        ) as spy:
            embedder.encode_batch([seen_text, new_text])
            assert spy.call_count == 1
            sent_texts = spy.call_args.args[0]
            assert sent_texts == [new_text]

    def test_text_hash_strips_whitespace(self, embedder: Embedder) -> None:
        h1 = embedder._text_hash("hello world")
        h2 = embedder._text_hash("hello world  ")
        h3 = embedder._text_hash("  hello world")
        assert h1 == h2 == h3
        assert len(h1) == 64

    def test_save_and_load_cache(self, tmp_path: Path) -> None:
        emb1 = Embedder()
        emb1.encode_single("persistence test text")
        cache_path = tmp_path / "cache.pkl"
        emb1.save_cache(str(cache_path))
        assert cache_path.exists()

        emb2 = Embedder()
        emb2.load_cache(str(cache_path))
        with patch.object(emb2._model, "encode") as spy:
            v = emb2.encode_single("persistence test text")
            assert spy.call_count == 0
            assert v.shape == (EMBEDDING_DIM,)


class TestEmbedderVersion:
    def test_model_version_string(self, embedder: Embedder) -> None:
        version = embedder.model_version
        assert embedder.model_name in version
        assert "@" in version
