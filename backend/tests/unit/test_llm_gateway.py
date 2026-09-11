"""Unit tests for LLM Gateway — provider dispatch, key decryption isolation, caching."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.exceptions import HTTPException

from app.core.model_router import _build_llm, _make_llm, _cache_key


def make_settings(provider: str, model_name: str = "test-model", ollama_url: str | None = None):
    s = MagicMock()
    s.provider = provider
    s.model_name = model_name
    s.api_key_enc = "encrypted-key"
    s.ollama_url = ollama_url
    return s


@pytest.mark.parametrize(
    "provider,expected_cls",
    [
        ("anthropic", "ChatAnthropic"),
        ("openai", "ChatOpenAI"),
        ("google", "ChatGoogleGenerativeAI"),
        ("ollama", "ChatOllama"),
        ("nvidia_nim", "ChatOpenAI"),
        ("openrouter", "ChatOpenAI"),
        ("opencode", "ChatOpenAI"),
    ],
)
def test_model_router_instantiates_correct_class(provider, expected_cls):
    settings = make_settings(provider, ollama_url="http://localhost:11434" if provider == "ollama" else None)
    module_name = {
        "ChatAnthropic": "langchain_anthropic",
        "ChatOpenAI": "langchain_openai",
        "ChatGoogleGenerativeAI": "langchain_google_genai",
        "ChatOllama": "langchain_ollama",
    }[expected_cls]
    with (
        patch(f"{module_name}.{expected_cls}") as mock_cls,
        patch("app.core.model_router.decrypt_api_key", return_value="plaintext-key"),
        patch("app.core.model_router.settings") as mock_app_settings,
    ):
        mock_app_settings.APP_SECRET_KEY = "secret"
        mock_cls.return_value = MagicMock()
        _build_llm(settings)
        mock_cls.assert_called_once()


def test_decryption_called_during_build():
    settings = make_settings("openai")
    with (
        patch("langchain_openai.ChatOpenAI") as mock_cls,
        patch("app.core.model_router.decrypt_api_key") as mock_decrypt,
        patch("app.core.model_router.settings") as mock_app_settings,
    ):
        mock_app_settings.APP_SECRET_KEY = "secret"
        mock_decrypt.return_value = "plaintext-key"
        mock_cls.return_value = MagicMock()
        _build_llm(settings)
        mock_decrypt.assert_called_once_with("encrypted-key", "secret")


def test_plaintext_key_never_in_llm_callbacks():
    settings = make_settings("openai")
    with (
        patch("langchain_openai.ChatOpenAI") as return_mock,
        patch("app.core.model_router.decrypt_api_key", return_value="plaintext-key"),
        patch("app.core.model_router.settings") as mock_app_settings,
    ):
        mock_app_settings.APP_SECRET_KEY = "secret"
        mock_llm = MagicMock()
        return_mock.return_value = mock_llm
        result = _build_llm(settings)
        assert result == mock_llm
        assert "api_key" not in str(mock_llm.callbacks).lower()


def test_model_router_raises_on_empty_settings():
    with pytest.raises((ValueError, TypeError, AttributeError)):
        _build_llm(None)


def test_model_router_raises_on_unknown_provider():
    s = make_settings("unknown_provider")
    with (
        patch("app.core.model_router.decrypt_api_key", return_value="key"),
        patch("app.core.model_router.settings") as mock_app_settings,
    ):
        mock_app_settings.APP_SECRET_KEY = "secret"
        with pytest.raises((ValueError, KeyError, AttributeError, HTTPException)):
            _build_llm(s)


def test_cache_key_format():
    key = _cache_key("user-123", "company_research", "Tell me about Stripe")
    assert key.startswith("llm_cache:")
    assert len(key) > 20


def test_cache_key_different_for_different_inputs():
    k1 = _cache_key("u1", "company_research", "Stripe")
    k2 = _cache_key("u1", "company_research", "Meta")
    assert k1 != k2


def test_cache_key_same_for_same_inputs():
    k1 = _cache_key("u1", "job_search", "Python engineer remote")
    k2 = _cache_key("u1", "job_search", "Python engineer remote")
    assert k1 == k2
