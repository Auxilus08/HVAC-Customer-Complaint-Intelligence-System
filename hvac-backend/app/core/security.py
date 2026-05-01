"""PII stripping pipeline — regex patterns + spaCy NER.

Called in EXACTLY two places:
  1. Before any DB write    (complaint_service.py)
  2. Before any Claude API call (advisory_service.py, label_job.py)
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Regex patterns ────────────────────────────────────────────────────────────

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("phone_in", re.compile(r"\b(?:\+91[\s\-]?)?[6-9]\d{4}[\s\-]?\d{5}\b")),
    ("phone_generic", re.compile(r"\b\d{10,12}\b")),
    ("email", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    ("aadhaar", re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")),
    ("pan", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    ("credit_card", re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b")),
    ("pincode", re.compile(r"\b[1-9][0-9]{5}\b")),
    ("ip_addr", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
]

_REPLACEMENT = "[REDACTED]"

# Lazy-load spaCy model to avoid import-time overhead in workers
_nlp: Any = None


def _get_nlp() -> Any:
    global _nlp
    if _nlp is None:
        try:
            import spacy  # type: ignore[import]

            _nlp = spacy.load(
                "en_core_web_sm", disable=["parser", "tagger", "lemmatizer"]
            )
        except OSError:
            logger.warning("spacy_model_missing", model="en_core_web_sm")
            _nlp = False  # sentinel — regex-only fallback
    return _nlp


def strip_pii_regex(text: str) -> str:
    """Apply all regex-based PII patterns to *text* and return cleaned string."""
    for label, pattern in _PATTERNS:
        before = text
        text = pattern.sub(_REPLACEMENT, text)
        if text != before:
            logger.debug("pii_redacted_regex", pattern=label)
    return text


def strip_pii_ner(text: str) -> str:
    """Apply spaCy NER to redact PERSON / ORG / GPE / LOC / PHONE entities."""
    nlp = _get_nlp()
    if not nlp:
        return text  # fallback: regex already ran

    doc = nlp(text)
    _redact_labels = {"PERSON", "ORG", "GPE", "LOC", "PHONE", "CARDINAL"}
    result = text
    # Replace in reverse order to preserve offsets
    for ent in reversed(doc.ents):
        if ent.label_ in _redact_labels:
            result = result[: ent.start_char] + _REPLACEMENT + result[ent.end_char :]
            logger.debug("pii_redacted_ner", label=ent.label_)
    return result


def strip_pii(text: str) -> str:
    """Full PII stripping: regex first, then NER.

    This is the authoritative entrypoint — call this, not the sub-functions.
    """
    text = strip_pii_regex(text)
    text = strip_pii_ner(text)
    return text


# ── AES-256-GCM encryption for raw_text storage ───────────────────────────────


def _get_encryption_key() -> bytes:
    from app.config import get_settings

    raw = get_settings().RAW_TEXT_ENCRYPTION_KEY
    if not raw:
        raise OSError("RAW_TEXT_ENCRYPTION_KEY is not set")
    return base64.b64decode(raw)


def encrypt_raw_text(plaintext: str) -> bytes:
    """Encrypt *plaintext* with AES-256-GCM; returns nonce‖ciphertext‖tag."""
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ciphertext


def decrypt_raw_text(blob: bytes) -> str:
    """Decrypt blob produced by *encrypt_raw_text*."""
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce, ciphertext = blob[:12], blob[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


def compute_text_hash(text: str) -> str:
    """SHA-256 hex digest of *text* — used as embedding cache key."""
    return hashlib.sha256(text.encode()).hexdigest()
