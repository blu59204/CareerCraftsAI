import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.model_router import _build_llm
from app.models.db import UserModelSettings


def make_settings(provider: str, model_name: str = "test-model", ollama_url: str | None = None):
    s = MagicMock(spec=UserModelSettings)
    s.provider = provider
    s.model_name = model_name
    s.api_key_enc = "encrypted-key"
    s.ollama_url = ollama_url
    return s


@pytest.mark.parametrize(
    "provider,expected_class_path",
    [
        ("anthropic", "langchain_anthropic.ChatAnthropic"),
        ("openai", "langchain_openai.ChatOpenAI"),
        ("google", "langchain_google_genai.ChatGoogleGenerativeAI"),
        ("ollama", "langchain_ollama.ChatOllama"),
        ("nvidia_nim", "langchain_openai.ChatOpenAI"),
    ],
)
def test_model_router_dispatches_correct_class(provider, expected_class_path):
    settings = make_settings(
        provider, ollama_url="http://localhost:11434" if provider == "ollama" else None
    )
    module, cls = expected_class_path.rsplit(".", 1)
    with (
        patch(f"{module}.{cls}") as mock_cls,
        patch("app.core.model_router.decrypt_api_key", return_value="plaintext-key"),
        patch("app.core.model_router.settings") as mock_app_settings,
    ):
        mock_app_settings.APP_SECRET_KEY = "secret"
        mock_cls.return_value = MagicMock()
        _build_llm(settings)
        mock_cls.assert_called_once()


def test_model_router_raises_when_no_settings():
    with pytest.raises((ValueError, TypeError, AttributeError)):
        _build_llm(None)


def test_model_router_raises_on_unknown_provider():
    s = make_settings("unknown_provider")
    with (
        patch("app.core.model_router.decrypt_api_key", return_value="key"),
        patch("app.core.model_router.settings") as mock_app_settings,
    ):
        mock_app_settings.APP_SECRET_KEY = "secret"
        from fastapi.exceptions import HTTPException
        with pytest.raises((ValueError, KeyError, AttributeError, HTTPException)):
            _build_llm(s)
