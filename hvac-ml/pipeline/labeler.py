"""Cluster auto-labeling via Gemini API with Jaccard membership gate.

Single source of truth for Jaccard membership logic. hvac-backend's label_job
MUST import this class — no local Jaccard re-implementation.

The Jaccard gate avoids unnecessary LLM calls: if a cluster's member set has
not drifted by more than the threshold (default 0.2 = 20% set difference),
the previous label is reused. PII stripping happens before any text leaves
the process for Gemini.
"""

from __future__ import annotations

import os
import re

import google.generativeai as genai
import structlog

logger = structlog.get_logger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_JACCARD_THRESHOLD = 0.2

_LABEL_SYSTEM_PROMPT = (
    "These HVAC complaints belong to the same pattern. "
    "Give a 3-5 word label describing the common issue. "
    "Return ONLY the label, no punctuation, no quotes."
)

# PII patterns — matched before sending samples to Gemini.
_PII_PATTERNS = [
    re.compile(r"\b(?:\+91[\s\-]?)?[6-9]\d{9}\b"),                 # Indian mobile
    re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),  # email
    re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"),              # Aadhaar
    re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),                      # PAN
]


def _strip_pii(text: str) -> str:
    for pattern in _PII_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


class ClusterLabeler:
    """Labels clusters via Gemini API, gated by Jaccard membership distance.

    Args:
        model:             Gemini model id used for labeling.
        jaccard_threshold: Distance > threshold ⇒ relabel; <= ⇒ reuse.
        api_key:           Google API key. Falls back to GOOGLE_API_KEY.
        sample_limit:      Max representative complaints sent per cluster.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        jaccard_threshold: float = DEFAULT_JACCARD_THRESHOLD,
        api_key: str | None = None,
        sample_limit: int = 10,
    ) -> None:
        self.model = model
        self.jaccard_threshold = jaccard_threshold
        self.sample_limit = sample_limit
        _key = api_key or os.environ.get("GOOGLE_API_KEY", "")

        # genai.configure() sets the API key GLOBALLY at the module level —
        # a second ClusterLabeler with a different key silently clobbers the
        # first. Guard against this until we migrate to google.genai.Client().
        if not hasattr(genai, "_hvac_configured_key"):
            genai.configure(api_key=_key)
            genai._hvac_configured_key = _key  # type: ignore[attr-defined]
        elif genai._hvac_configured_key != _key:  # type: ignore[attr-defined]
            raise RuntimeError(
                "Cannot create ClusterLabeler with a different API key — "
                "google.generativeai.configure() is module-global. "
                "Use the same key or restart the process."
            )

        self._client = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=_LABEL_SYSTEM_PROMPT,
        )

    # ── Jaccard logic ─────────────────────────────────────────────────────
    def jaccard_distance(
        self, old_fingerprint: set[int], new_fingerprint: set[int]
    ) -> float:
        """Jaccard distance = 1 - |intersection| / |union|.

        Returns 0.0 for identical sets and 1.0 for fully disjoint sets.
        Two empty sets are considered identical (distance 0).
        """
        if not old_fingerprint and not new_fingerprint:
            return 0.0
        intersection = len(old_fingerprint & new_fingerprint)
        union = len(old_fingerprint | new_fingerprint)
        return 1.0 - intersection / union

    def should_relabel(
        self, old_fp: set[int], new_fp: set[int]
    ) -> bool:
        """Returns True if Jaccard distance strictly exceeds threshold."""
        return self.jaccard_distance(old_fp, new_fp) > self.jaccard_threshold

    # ── Gemini API call ───────────────────────────────────────────────────
    def label_cluster(self, complaints: list[str]) -> str:
        """Send up to *sample_limit* complaints to Gemini and return a label.

        Complaints are PII-stripped before leaving the process.
        """
        samples = [_strip_pii(t) for t in complaints[: self.sample_limit]]
        user_msg = "Complaint samples:\n" + "\n".join(f"- {s}" for s in samples)

        response = self._client.generate_content(
            user_msg,
            generation_config=genai.GenerationConfig(
                max_output_tokens=40,
                temperature=0.2,
            ),
        )
        label = response.text.strip().strip('"').strip("'")
        return label

    # ── Batch labeling with Jaccard gate ──────────────────────────────────
    def label_all_clusters(
        self,
        cluster_complaints: dict[int, list[str]],
        old_fingerprints: dict[int, set[int]] | None = None,
        new_fingerprints: dict[int, set[int]] | None = None,
        previous_labels: dict[int, str] | None = None,
    ) -> dict[int, str]:
        """Label all clusters, skipping unchanged ones via the Jaccard gate.

        Args:
            cluster_complaints: cluster_id → representative complaint texts.
            old_fingerprints:   previous run's member-id sets (or None).
            new_fingerprints:   current run's member-id sets (or None).
            previous_labels:    previous labels keyed by cluster_id.

        Returns: cluster_id → label, including reused labels for skipped
        clusters.
        """
        old_fingerprints = old_fingerprints or {}
        new_fingerprints = new_fingerprints or {}
        previous_labels = previous_labels or {}

        labels: dict[int, str] = {}
        relabeled = 0
        skipped = 0

        for cluster_id, samples in cluster_complaints.items():
            old_fp = old_fingerprints.get(cluster_id)
            new_fp = new_fingerprints.get(cluster_id)

            # Reuse previous label only when:
            #   - we have all three (old fp, new fp, previous label), AND
            #   - the Jaccard gate says no relabel needed.
            if (
                old_fp is not None
                and new_fp is not None
                and cluster_id in previous_labels
                and not self.should_relabel(old_fp, new_fp)
            ):
                labels[cluster_id] = previous_labels[cluster_id]
                skipped += 1
                continue

            try:
                label = self.label_cluster(samples)
            except Exception as exc:
                logger.error(
                    "labeler_api_error",
                    cluster_id=cluster_id,
                    error=str(exc),
                )
                if cluster_id in previous_labels:
                    labels[cluster_id] = previous_labels[cluster_id]
                continue

            labels[cluster_id] = label
            relabeled += 1
            logger.info(
                "cluster_labeled",
                cluster_id=cluster_id,
                label=label,
                samples=len(samples),
            )

        logger.info(
            "labeler_run_complete",
            total=len(cluster_complaints),
            relabeled=relabeled,
            skipped=skipped,
        )
        return labels
