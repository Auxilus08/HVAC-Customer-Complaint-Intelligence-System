"""Unified LLM client factory for DeepSeek, Qwen, and Gemini providers.

All three expose OpenAI-compatible chat-completions endpoints, so one
openai.OpenAI client (with a provider-specific base_url) covers all cases.
"""

from __future__ import annotations

from openai import OpenAI

from app.config import get_settings


def get_llm_client() -> tuple[OpenAI, str]:
    """Return (configured OpenAI client, model name) for the active provider."""
    settings = get_settings()
    provider = settings.LLM_PROVIDER

    if provider == "deepseek":
        if not settings.DEEPSEEK_API_KEY:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is not configured. Set it in .env to use the deepseek provider."
            )
        return (
            OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL),
            settings.DEEPSEEK_MODEL,
        )

    if provider == "qwen":
        if not settings.QWEN_API_KEY:
            raise RuntimeError(
                "QWEN_API_KEY is not configured. Set it in .env to use the qwen provider."
            )
        return (
            OpenAI(api_key=settings.QWEN_API_KEY, base_url=settings.QWEN_BASE_URL),
            settings.QWEN_MODEL,
        )

    if provider == "gemini":
        if not settings.GOOGLE_API_KEY:
            raise RuntimeError(
                "GOOGLE_API_KEY is not configured. Set it in .env to use the gemini provider."
            )
        return (
            OpenAI(api_key=settings.GOOGLE_API_KEY, base_url=settings.GEMINI_BASE_URL),
            settings.GEMINI_MODEL,
        )

    # Unreachable — field_validator ensures provider is always a known value.
    raise RuntimeError(f"Unknown LLM_PROVIDER: {provider!r}")


def get_vision_client() -> tuple[OpenAI, str]:
    """Return (OpenAI client, vision-model name) for image inputs.

    Only Qwen is currently wired for vision — DeepSeek and Gemini fall back
    to the text model since they don't have a separate vision endpoint on
    this codebase yet. Raise RuntimeError if the provider isn't configured.
    """
    settings = get_settings()
    provider = settings.LLM_PROVIDER

    if provider == "qwen":
        if not settings.QWEN_API_KEY:
            raise RuntimeError(
                "QWEN_API_KEY is not configured. Set it in .env to use the qwen provider."
            )
        return (
            OpenAI(api_key=settings.QWEN_API_KEY, base_url=settings.QWEN_BASE_URL),
            settings.QWEN_VISION_MODEL,
        )

    # Gemini supports multimodal natively via its OpenAI-compatible endpoint
    if provider == "gemini":
        if not settings.GOOGLE_API_KEY:
            raise RuntimeError(
                "GOOGLE_API_KEY is not configured. Set it in .env to use the gemini provider."
            )
        return (
            OpenAI(api_key=settings.GOOGLE_API_KEY, base_url=settings.GEMINI_BASE_URL),
            settings.GEMINI_MODEL,
        )

    # DeepSeek's OpenAI-compatible API doesn't accept image inputs.
    raise RuntimeError(
        f"Vision is not supported for LLM_PROVIDER={provider!r}. "
        "Switch LLM_PROVIDER to 'qwen' or 'gemini' to enable image analysis."
    )


def get_provider_info() -> dict[str, str]:
    """Return diagnostic info for the active provider (no live API call)."""
    settings = get_settings()
    provider = settings.LLM_PROVIDER

    mapping: dict[str, dict[str, str]] = {
        "deepseek": {
            "provider": "deepseek",
            "model": settings.DEEPSEEK_MODEL,
            "base_url": settings.DEEPSEEK_BASE_URL,
        },
        "qwen": {
            "provider": "qwen",
            "model": settings.QWEN_MODEL,
            "base_url": settings.QWEN_BASE_URL,
        },
        "gemini": {
            "provider": "gemini",
            "model": settings.GEMINI_MODEL,
            "base_url": settings.GEMINI_BASE_URL,
        },
    }
    return mapping[provider]
