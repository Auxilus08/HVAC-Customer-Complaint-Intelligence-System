"""SentenceTransformer wrapper with SHA-256 text-hash caching.

Caches every encode by SHA-256 of the stripped text so repeated complaint
text never re-runs the model. Cache can be persisted to disk via pickle for
warm starts. This is the SINGLE source of truth for embedding logic —
backend workers MUST import this class instead of using SentenceTransformer
directly.
"""

from __future__ import annotations

import hashlib
import pickle
from pathlib import Path

import numpy as np
import structlog
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger(__name__)

EMBEDDING_DIM: int = 384


class Embedder:
    """Wraps sentence-transformers for HVAC complaint embedding.

    Caches by SHA-256 of stripped text — never recomputes the same text.
    Embeddings are L2-normalised so cosine similarity reduces to dot product.
    """

    def __init__(
        self,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        cache_dir: str | None = None,
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._model = SentenceTransformer(model_name, device=device)
        self._cache: dict[str, np.ndarray] = {}
        self._cache_dir = Path(cache_dir) if cache_dir else None

        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            default_cache = self._cache_dir / "embedder_cache.pkl"
            if default_cache.exists():
                self.load_cache(str(default_cache))

    # ── Hashing ────────────────────────────────────────────────────────────
    @staticmethod
    def _normalize(text: str) -> str:
        return text.strip()

    def _text_hash(self, text: str) -> str:
        """SHA-256 hash of stripped text (whitespace only — no case folding)."""
        return hashlib.sha256(self._normalize(text).encode("utf-8")).hexdigest()

    # ── Encoding ───────────────────────────────────────────────────────────
    def encode_single(self, text: str) -> np.ndarray:
        """Encode a single complaint, returning a (384,) L2-normalised vector.

        Returns the cached vector if the same stripped text has been seen.
        """
        key = self._text_hash(text)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        vector = self._model.encode(
            [text], normalize_embeddings=True, show_progress_bar=False
        )[0].astype(np.float32)
        self._cache[key] = vector
        return vector

    def encode_batch(
        self, texts: list[str], batch_size: int = 64
    ) -> np.ndarray:
        """Encode a list of complaints, returning an (N, 384) matrix.

        Per-text cache lookup — only uncached texts are sent to the model.
        Returned ordering matches *texts*.
        """
        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)

        result = np.zeros((len(texts), EMBEDDING_DIM), dtype=np.float32)
        uncached_idx: list[int] = []
        uncached_texts: list[str] = []
        keys: list[str] = []

        for i, text in enumerate(texts):
            key = self._text_hash(text)
            keys.append(key)
            cached = self._cache.get(key)
            if cached is not None:
                result[i] = cached
            else:
                uncached_idx.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            logger.debug(
                "embedder_encode_batch",
                total=len(texts),
                uncached=len(uncached_texts),
                cache_hits=len(texts) - len(uncached_texts),
            )
            new_vectors = self._model.encode(
                uncached_texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=len(uncached_texts) > 200,
            ).astype(np.float32)

            for offset, idx in enumerate(uncached_idx):
                vec = new_vectors[offset]
                result[idx] = vec
                self._cache[keys[idx]] = vec

        return result

    # ── Cache persistence ──────────────────────────────────────────────────
    def save_cache(self, path: str) -> None:
        """Persist the in-memory cache to *path* via pickle."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("wb") as f:
            pickle.dump(
                {"model_name": self.model_name, "cache": self._cache}, f
            )
        logger.info(
            "embedder_cache_saved", path=str(out), entries=len(self._cache)
        )

    def load_cache(self, path: str) -> None:
        """Load a previously persisted cache from *path*.

        If the cache was built by a different model the load is skipped so
        embedding dimensions and semantics stay consistent.
        """
        in_path = Path(path)
        if not in_path.exists():
            logger.warning("embedder_cache_missing", path=str(in_path))
            return
        with in_path.open("rb") as f:
            payload = pickle.load(f)  # noqa: S301 - trusted local file
        if payload.get("model_name") != self.model_name:
            logger.warning(
                "embedder_cache_model_mismatch",
                cache_model=payload.get("model_name"),
                current_model=self.model_name,
            )
            return
        self._cache.update(payload["cache"])
        logger.info(
            "embedder_cache_loaded", path=str(in_path), entries=len(self._cache)
        )

    # ── Introspection ──────────────────────────────────────────────────────
    @property
    def model_version(self) -> str:
        """Return model name + short hash for version tracking."""
        h = hashlib.sha256(self.model_name.encode()).hexdigest()[:8]
        return f"{self.model_name}@{h}"

    @property
    def cache_size(self) -> int:
        return len(self._cache)
