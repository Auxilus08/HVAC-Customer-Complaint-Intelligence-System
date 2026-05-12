"""Unit tests for the LLM client factory."""

from __future__ import annotations

import pytest
from openai import OpenAI
from pydantic import ValidationError

from app.services.llm_client import get_llm_client


def _make_settings(**overrides):
    """Construct a fresh Settings instance ignoring any .env file."""
    from app.config import Settings

    base = {
        "LLM_PROVIDER": "deepseek",
        "DEEPSEEK_API_KEY": "sk-test-deepseek",
        "DEEPSEEK_MODEL": "deepseek-chat",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "QWEN_API_KEY": "sk-test-qwen",
        "QWEN_MODEL": "qwen-plus",
        "QWEN_BASE_URL": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "GOOGLE_API_KEY": "sk-test-gemini",
        "GEMINI_MODEL": "gemini-2.5-flash-lite",
        "GEMINI_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",
    }
    base.update(overrides)
    return Settings.model_construct(**base)


def test_deepseek_provider_returns_correct_client_and_model(monkeypatch):
    settings = _make_settings(LLM_PROVIDER="deepseek")
    monkeypatch.setattr("app.services.llm_client.get_settings", lambda: settings)

    client, model = get_llm_client()

    assert isinstance(client, OpenAI)
    assert model == "deepseek-chat"
    assert str(client.base_url).rstrip("/") == "https://api.deepseek.com"


def test_qwen_provider_returns_correct_client_and_model(monkeypatch):
    settings = _make_settings(LLM_PROVIDER="qwen")
    monkeypatch.setattr("app.services.llm_client.get_settings", lambda: settings)

    client, model = get_llm_client()

    assert isinstance(client, OpenAI)
    assert model == "qwen-plus"
    assert "dashscope" in str(client.base_url)


def test_gemini_provider_returns_correct_client_and_model(monkeypatch):
    settings = _make_settings(LLM_PROVIDER="gemini")
    monkeypatch.setattr("app.services.llm_client.get_settings", lambda: settings)

    client, model = get_llm_client()

    assert isinstance(client, OpenAI)
    assert model == "gemini-2.5-flash-lite"
    assert "generativelanguage.googleapis.com" in str(client.base_url)


def test_empty_key_raises_runtime_error_with_provider_name(monkeypatch):
    settings = _make_settings(LLM_PROVIDER="deepseek", DEEPSEEK_API_KEY="")
    monkeypatch.setattr("app.services.llm_client.get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="deepseek"):
        get_llm_client()


def test_empty_qwen_key_raises_runtime_error(monkeypatch):
    settings = _make_settings(LLM_PROVIDER="qwen", QWEN_API_KEY="")
    monkeypatch.setattr("app.services.llm_client.get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="qwen"):
        get_llm_client()


def test_empty_gemini_key_raises_runtime_error(monkeypatch):
    settings = _make_settings(LLM_PROVIDER="gemini", GOOGLE_API_KEY="")
    monkeypatch.setattr("app.services.llm_client.get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="gemini"):
        get_llm_client()


def test_invalid_llm_provider_raises_value_error():
    from app.config import Settings

    with pytest.raises((ValidationError, ValueError)):
        Settings(LLM_PROVIDER="openai", _env_file=None)  # type: ignore[call-arg]
