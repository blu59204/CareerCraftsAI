from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def test_native_provider_is_used():
    from app.services import rag_service

    settings = SimpleNamespace(provider="ollama", ollama_url="http://ollama:11434")
    with patch.object(rag_service, "OllamaEmbeddings", return_value="ollama") as embeddings:
        assert rag_service.get_embedding_provider(settings) == "ollama"
        assert rag_service.get_embedding_model(settings) == "ollama"
    embeddings.assert_called_once_with(model="nomic-embed-text", base_url="http://ollama:11434")


def test_non_native_provider_requires_explicit_fallback(monkeypatch):
    from app.services import rag_service

    monkeypatch.setattr(rag_service.app_settings, "EMBEDDING_PROVIDER", "")
    with pytest.raises(rag_service.EmbeddingUnavailable, match="EMBEDDING_PROVIDER"):
        rag_service.get_embedding_provider(SimpleNamespace(provider="anthropic"))


def test_non_native_provider_uses_effective_collection_provider(monkeypatch):
    from app.services import rag_service

    monkeypatch.setattr(rag_service.app_settings, "EMBEDDING_PROVIDER", "ollama")
    settings = SimpleNamespace(provider="anthropic", ollama_url="http://ollama:11434")
    assert rag_service.get_embedding_provider(settings) == "ollama"


def test_fallback_ollama_uses_configured_url_not_chat_settings(monkeypatch):
    # A DeepSeek model row has no ollama_url; the fallback must still reach
    # the configured Ollama server instead of localhost inside the container.
    from app.services import rag_service

    monkeypatch.setattr(rag_service.app_settings, "EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setattr(rag_service.app_settings, "EMBEDDING_OLLAMA_URL", "http://ollama:11434")
    settings = SimpleNamespace(provider="deepseek", ollama_url=None, api_key_enc="enc")
    with patch.object(rag_service, "OllamaEmbeddings", return_value="ollama") as embeddings:
        assert rag_service.get_embedding_model(settings) == "ollama"
    embeddings.assert_called_once_with(model="nomic-embed-text", base_url="http://ollama:11434")


def test_fallback_openai_never_reuses_the_chat_provider_key(monkeypatch):
    from app.services import rag_service

    monkeypatch.setattr(rag_service.app_settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(rag_service.app_settings, "EMBEDDING_API_KEY", "")
    decrypt = MagicMock(return_value="deepseek-key")
    monkeypatch.setattr(rag_service, "decrypt_api_key", decrypt)
    settings = SimpleNamespace(provider="deepseek", ollama_url=None, api_key_enc="enc")
    with pytest.raises(rag_service.EmbeddingUnavailable, match="EMBEDDING_API_KEY"):
        rag_service.get_embedding_model(settings)
    decrypt.assert_not_called()

    monkeypatch.setattr(rag_service.app_settings, "EMBEDDING_API_KEY", "sk-embed")
    with patch.object(rag_service, "OpenAIEmbeddings", return_value="openai") as embeddings:
        assert rag_service.get_embedding_model(settings) == "openai"
    embeddings.assert_called_once_with(model="text-embedding-3-small", api_key="sk-embed")
    decrypt.assert_not_called()


def test_native_openai_still_uses_the_users_key(monkeypatch):
    from app.services import rag_service

    monkeypatch.setattr(rag_service, "decrypt_api_key", MagicMock(return_value="sk-user"))
    settings = SimpleNamespace(provider="openai", ollama_url=None, api_key_enc="enc")
    with patch.object(rag_service, "OpenAIEmbeddings", return_value="openai") as embeddings:
        assert rag_service.get_embedding_model(settings) == "openai"
    embeddings.assert_called_once_with(model="text-embedding-3-small", api_key="sk-user")
