"""Cluster auto-labeling via LLM API with Jaccard membership gate.

Single source of truth for Jaccard membership logic. hvac-backend's label_job
MUST import this class — no local Jaccard re-implementation.

The Jaccard gate avoids unnecessary LLM calls: if a cluster's member set has
not drifted by more than the threshold (default 0.2 = 20% set difference),
the previous label is reused. PII stripping happens before any text leaves
the process for the LLM.

Primary path: pass a pre-built ``openai.OpenAI`` client via the ``client``
parameter (preferred — used by hvac-backend after migrating to multi-provider).
Legacy path: pass ``api_key`` (+ optional ``base_url`` / ``provider``) to keep
existing tests and direct invocations working without change.
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
    "You are labeling a cluster of HVAC service complaints. "
    "Describe the underlying TECHNICAL FAULT in the air-conditioning unit "
    "(e.g. 'Compressor noise outdoor unit', 'Refrigerant leak indoor coil', "
    "'Breaker trips on startup', 'Drain pan water overflow', "
    "'Installation pipe insulation missing'). "
    "Use 3-5 words. Do NOT describe the data itself — never use words like "
    "'duplicate', 'repeat', 'similar', 'multiple', 'building-wide', "
    "'complaints', 'reports', 'pattern'. "
    "Return ONLY the label, no punctuation, no quotes."
)

# PII patterns — matched before sending samples to the LLM.
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
    """Labels clusters via an LLM API, gated by Jaccard membership distance.

    Preferred constructor (multi-provider):
        ClusterLabeler(client=openai_client, model="deepseek-chat")

    Legacy constructor (gemini-only, kept for backward compatibility):
        ClusterLabeler(api_key="...", model="gemini-2.5-flash")
        ClusterLabeler(api_key="...", model="...", base_url="...", provider="qwen")

    Args:
        model:             Model id used for labeling.
        jaccard_threshold: Distance > threshold ⇒ relabel; <= ⇒ reuse.
        api_key:           Provider API key (legacy path only).
        sample_limit:      Max representative complaints sent per cluster.
        client:            Pre-built openai.OpenAI instance (preferred path).
        base_url:          Override base URL (legacy path, triggers OpenAI SDK).
        provider:          Provider name hint for legacy path routing.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        jaccard_threshold: float = DEFAULT_JACCARD_THRESHOLD,
        api_key: str | None = None,
        sample_limit: int = 10,
        client: object | None = None,
        base_url: str | None = None,
        provider: str = "gemini",
    ) -> None:
        self.model = model
        self.jaccard_threshold = jaccard_threshold
        self.sample_limit = sample_limit

        if client is not None:
            # Preferred path: caller supplies a ready-made openai.OpenAI client.
            self._openai_client = client
            self._use_openai = True
        elif base_url is not None or provider != "gemini":
            # Legacy path with explicit base_url or non-gemini provider string.
            from openai import OpenAI

            _key = api_key or os.environ.get("GOOGLE_API_KEY", "")
            self._openai_client = OpenAI(api_key=_key, base_url=base_url)
            self._use_openai = True
        else:
            # Legacy gemini-only path — preserves existing test behaviour.
            _key = api_key or os.environ.get("GOOGLE_API_KEY", "")
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
            self._use_openai = False

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

    # ── LLM API call ──────────────────────────────────────────────────────
    def label_cluster(self, complaints: list[str]) -> str:
        """Send up to *sample_limit* complaints to the LLM and return a label.

        Complaints are PII-stripped before leaving the process.
        """
        samples = [_strip_pii(t) for t in complaints[: self.sample_limit]]
        user_msg = "Complaint samples:\n" + "\n".join(f"- {s}" for s in samples)

        if self._use_openai:
            from openai import OpenAI  # noqa: F401 — type hint only

            response = self._openai_client.chat.completions.create(  # type: ignore[union-attr]
                model=self.model,
                messages=[
                    {"role": "system", "content": _LABEL_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=40,
                temperature=0.2,
            )
            label = (response.choices[0].message.content or "").strip().strip('"').strip("'")
        else:
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
