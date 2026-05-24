from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_embeddings():
    emb = MagicMock()
    emb.embed_documents.return_value = [[0.1] * 384, [0.2] * 384]
    emb.embed_query.return_value = [0.15] * 384
    return emb


def test_extract_text_from_txt():
    from app.services.rag_service import extract_text
    content = b"Hello world, this is a resume."
    result = extract_text(content, "resume.txt")
    assert "Hello world" in result


def test_chunk_text_produces_multiple_chunks():
    from app.services.rag_service import chunk_text
    long_text = " ".join(["word"] * 1000)
    chunks = chunk_text(long_text)
    assert len(chunks) > 1


def test_get_embedding_model_anthropic_falls_back_to_ollama():
    from app.services.rag_service import get_embedding_model
    settings_mock = MagicMock()
    settings_mock.provider = "anthropic"
    settings_mock.ollama_url = None
    with patch("app.services.rag_service.OllamaEmbeddings") as mock_ollama:
        mock_ollama.return_value = MagicMock()
        get_embedding_model(settings_mock)
        mock_ollama.assert_called_once_with(model="nomic-embed-text")


def test_get_embedding_model_openai():
    from app.services.rag_service import get_embedding_model
    settings_mock = MagicMock()
    settings_mock.provider = "openai"
    settings_mock.api_key_enc = "encrypted"
    with patch("app.services.rag_service.OpenAIEmbeddings") as mock_emb, \
         patch("app.services.rag_service.decrypt_api_key", return_value="real-key"), \
         patch("app.services.rag_service.app_settings") as mock_cfg:
        mock_cfg.APP_SECRET_KEY = "secret"
        mock_emb.return_value = MagicMock()
        get_embedding_model(settings_mock)
        mock_emb.assert_called_once()


def test_collection_name_format():
    from app.services.rag_service import collection_name
    assert collection_name("usr_abc123", "resume") == "usr_abc123_resume"
    assert collection_name("usr_abc123", "jd") == "usr_abc123_jd"
