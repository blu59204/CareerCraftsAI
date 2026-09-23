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
