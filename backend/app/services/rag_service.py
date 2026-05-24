import io
import logging
from functools import lru_cache

from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings as app_settings
from app.core.security import decrypt_api_key

logger = logging.getLogger(__name__)

# Embedding dimension per provider — must match model output
EMBEDDING_DIMENSIONS: dict[str, int] = {
    "openai": 1536,    # text-embedding-3-small
    "google": 768,     # models/embedding-001
    "ollama": 768,     # nomic-embed-text
    "anthropic": 768,  # falls back to nomic-embed-text
    "nvidia_nim": 768, # falls back to nomic-embed-text
}


def collection_name(user_id: str, doc_type: str) -> str:
    return f"{user_id}_{doc_type}"


def extract_text(content: bytes, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        import fitz  # PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    if lower.endswith(".docx"):
        from docx import Document as DocxDocument
        doc = DocxDocument(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    return content.decode("utf-8", errors="replace")


def chunk_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    return splitter.split_text(text)


def get_embedding_model(model_settings):
    provider = model_settings.provider
    if provider == "openai":
        api_key = decrypt_api_key(model_settings.api_key_enc, app_settings.APP_SECRET_KEY)
        return OpenAIEmbeddings(model="text-embedding-3-small", api_key=api_key)
    if provider == "google":
        api_key = decrypt_api_key(model_settings.api_key_enc, app_settings.APP_SECRET_KEY)
        return GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=api_key)
    if provider == "ollama":
        return OllamaEmbeddings(model="nomic-embed-text", base_url=model_settings.ollama_url)
    # anthropic + nvidia_nim have no native embedding API — fall back to local nomic-embed-text
    return OllamaEmbeddings(model="nomic-embed-text")


@lru_cache(maxsize=1)
def _get_pg_engine(connection_string: str):
    """Cache PGEngine per connection string — avoids creating new connection pool per call."""
    from langchain_postgres.v2.engine import PGEngine
    return PGEngine.from_connection_string(url=connection_string)


def _psycopg_url() -> str:
    """Convert asyncpg URL to psycopg3 URL for langchain-postgres."""
    url = app_settings.DATABASE_URL
    return url.replace("+asyncpg", "+psycopg")


def get_vector_store(user_id: str, doc_type: str, embeddings, provider: str = "openai"):
    """Get or create PGVectorStore for a user+doc_type collection."""
    from langchain_postgres.v2.vectorstores import PGVectorStore
    table = collection_name(user_id, doc_type)
    engine = _get_pg_engine(_psycopg_url())
    dim = EMBEDDING_DIMENSIONS.get(provider, 768)
    try:
        engine.init_vectorstore_table(table_name=table, vector_size=dim, overwrite_existing=False)
    except Exception as exc:
        logger.debug("init_vectorstore_table skipped for %s (likely exists): %s", table, exc)
    return PGVectorStore.create_sync(
        engine=engine,
        table_name=table,
        embedding_service=embeddings,
    )


def ingest_document(
    user_id: str,
    doc_type: str,
    text: str,
    metadata: dict,
    model_settings,
) -> int:
    """Chunk, embed, store. Returns chunk count."""
    chunks = chunk_text(text)
    embeddings = get_embedding_model(model_settings)
    docs = [
        Document(page_content=chunk, metadata={**metadata, "chunk_index": i})
        for i, chunk in enumerate(chunks)
    ]
    store = get_vector_store(user_id, doc_type, embeddings, provider=model_settings.provider)
    store.add_documents(docs)
    return len(docs)


def retrieve(
    user_id: str,
    doc_type: str,
    query: str,
    model_settings,
    k: int = 5,
) -> list[Document]:
    """Retrieve top-k relevant chunks."""
    embeddings = get_embedding_model(model_settings)
    store = get_vector_store(user_id, doc_type, embeddings, provider=model_settings.provider)
    return store.similarity_search(query, k=k)
