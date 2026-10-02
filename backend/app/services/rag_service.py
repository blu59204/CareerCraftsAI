import io
import logging

from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings as app_settings
from app.core.security import decrypt_api_key

logger = logging.getLogger(__name__)


class EmbeddingUnavailable(RuntimeError):
    pass


OLLAMA_EMBEDDING_MODEL = "qwen3-embedding:0.6b"
GOOGLE_EMBEDDING_MODEL = "models/gemini-embedding-001"
GOOGLE_EMBEDDING_DIMENSIONS = 768
# Qwen3-Embedding is instruction-aware: queries carry a one-line task, documents
# are embedded bare (per the model card).
QWEN_QUERY_TASK = (
    "Given a job description or role, retrieve relevant passages from the candidate's documents"
)
DEFAULT_OLLAMA_URL = "http://localhost:11434"

# Vector size per *effective* embedding provider -- collection_name() is always
# called with get_embedding_provider()'s result (openai, google or ollama),
# never with a chat-only provider such as anthropic or deepseek.
EMBEDDING_DIMENSIONS: dict[str, int] = {
    "openai": 1536,  # text-embedding-3-small
    "google": GOOGLE_EMBEDDING_DIMENSIONS,  # gemini-embedding-001, truncated to 768
    "ollama": 1024,  # qwen3-embedding:0.6b
}


class QwenOllamaEmbeddings(OllamaEmbeddings):
    """OllamaEmbeddings that adds Qwen3-Embedding's query instruction."""

    query_task: str = QWEN_QUERY_TASK

    def _instruct(self, text: str) -> str:
        return f"Instruct: {self.query_task}\nQuery:{text}"

    def embed_query(self, text: str) -> list[float]:
        return super().embed_query(self._instruct(text))

    async def aembed_query(self, text: str) -> list[float]:
        return await super().aembed_query(self._instruct(text))


class GeminiEmbeddings(GoogleGenerativeAIEmbeddings):
    """gemini-embedding-001 truncated to GOOGLE_EMBEDDING_DIMENSIONS.

    langchain-google-genai 2.1.x only takes output_dimensionality per call, so
    it is defaulted here to keep the existing 768-d google collections valid.
    """

    def embed_documents(self, texts, **kwargs):
        kwargs.setdefault("output_dimensionality", GOOGLE_EMBEDDING_DIMENSIONS)
        return super().embed_documents(texts, **kwargs)

    def embed_query(self, text, **kwargs):
        kwargs.setdefault("output_dimensionality", GOOGLE_EMBEDDING_DIMENSIONS)
        return super().embed_query(text, **kwargs)

    async def aembed_documents(self, texts, **kwargs):
        kwargs.setdefault("output_dimensionality", GOOGLE_EMBEDDING_DIMENSIONS)
        return await super().aembed_documents(texts, **kwargs)

    async def aembed_query(self, text, **kwargs):
        kwargs.setdefault("output_dimensionality", GOOGLE_EMBEDDING_DIMENSIONS)
        return await super().aembed_query(text, **kwargs)


def collection_name(user_id: str, doc_type: str, provider: str = "openai") -> str:
    """Generate collection name namespaced by user, doc_type, and embedding provider.

    Provider namespacing prevents dimension mismatch when users switch between
    providers with different embedding dimensions (e.g., OpenAI 1536-d vs Google 768-d).
    """
    # Map provider to dimension to ensure collections are separated by embedding size
    dimension = EMBEDDING_DIMENSIONS.get(provider, 768)
    return f"{user_id}_{doc_type}_{provider}_{dimension}d"


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
    """Embeddings for the user's active model, or the deployment fallback.

    Providers without an embeddings API (DeepSeek, Anthropic, OpenRouter,
    NVIDIA NIM) use EMBEDDING_PROVIDER. The fallback never reuses the chat
    provider's API key -- a DeepSeek key sent to OpenAI would just 401 -- so
    it needs its own EMBEDDING_API_KEY (openai/google) or EMBEDDING_OLLAMA_URL.
    """
    provider = get_embedding_provider(model_settings)
    native = model_settings.provider == provider
    if provider in {"openai", "google"}:
        if native:
            api_key = decrypt_api_key(model_settings.api_key_enc, app_settings.APP_SECRET_KEY)
        else:
            api_key = app_settings.EMBEDDING_API_KEY.strip()
            if not api_key:
                raise EmbeddingUnavailable(
                    f"EMBEDDING_PROVIDER={provider} needs EMBEDDING_API_KEY for "
                    f"'{model_settings.provider}' models."
                )
        if provider == "openai":
            return OpenAIEmbeddings(model="text-embedding-3-small", api_key=api_key)
        return GeminiEmbeddings(model=GOOGLE_EMBEDDING_MODEL, google_api_key=api_key)
    if provider == "ollama":
        # The user's own Ollama when they chose it; otherwise the operator's
        # EMBEDDING_OLLAMA_URL (a trusted server setting, so not subject to the
        # per-user OLLAMA_ALLOWED_HOSTS check).
        base_url = (
            (model_settings.ollama_url if native else None)
            or app_settings.EMBEDDING_OLLAMA_URL.strip()
            or DEFAULT_OLLAMA_URL
        )
        return QwenOllamaEmbeddings(model=OLLAMA_EMBEDDING_MODEL, base_url=base_url)
    raise EmbeddingUnavailable(f"Unsupported embedding provider: {provider}")


def get_embedding_provider(model_settings) -> str:
    provider = model_settings.provider
    if provider in {"openai", "google", "ollama"}:
        return provider
    fallback = app_settings.EMBEDDING_PROVIDER.strip().lower()
    if fallback not in {"openai", "google", "ollama"}:
        raise EmbeddingUnavailable(
            f"Provider '{provider}' has no embeddings API and EMBEDDING_PROVIDER is unset. "
            "Set EMBEDDING_PROVIDER to openai, google, or ollama."
        )
    return fallback


def _psycopg_url() -> str:
    """Convert asyncpg URL to psycopg3 URL for langchain-postgres PGVector."""
    url = app_settings.DATABASE_URL
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "+psycopg")
    if "postgresql://" in url and "+psycopg" not in url:
        logger.warning(
            "DATABASE_URL does not contain '+asyncpg' driver prefix. "
            "Assuming psycopg3 compatibility — verify your connection string."
        )
        return url.replace("postgresql://", "postgresql+psycopg://")
    return url


def get_vector_store(user_id: str, doc_type: str, embeddings, provider: str = "openai"):
    """Get or create PGVector store for a user+doc_type+provider collection.

    Provider is included in the collection name to prevent dimension mismatch
    when users switch between embedding providers.
    """
    from langchain_postgres import PGVector

    table = collection_name(user_id, doc_type, provider)
    return PGVector(
        connection=_psycopg_url(),
        collection_name=table,
        embeddings=embeddings,
        use_jsonb=True,
    )


def _ensure_hnsw_index() -> None:
    """Create the LangChain embedding HNSW index after the table exists."""
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(_psycopg_url(), pool_pre_ping=True)
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_langchain_embedding_hnsw
                    ON public.langchain_pg_embedding
                    USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64)
                """))
        finally:
            engine.dispose()
    except Exception as exc:
        logger.warning("Failed to ensure langchain_pg_embedding HNSW index: %s", exc)


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
    store = get_vector_store(
        user_id, doc_type, embeddings, provider=get_embedding_provider(model_settings)
    )
    store.add_documents(docs)
    _ensure_hnsw_index()
    return len(docs)


def retrieve(
    user_id: str,
    doc_type: str,
    query: str,
    model_settings,
    k: int = 5,
) -> list[Document]:
    """Retrieve top-k relevant chunks."""
    if doc_type == "resume":
        # A resume the member picked for this run replaces similarity search:
        # vectors carry no document id, so other resumes would leak into the context.
        from app.core.sync_db import fetch_chosen_resume

        chosen = fetch_chosen_resume(user_id)
        if chosen is not None and chosen.raw_text:
            return [Document(page_content=c, metadata={"doc_type": "resume"})
                    for c in chunk_text(chosen.raw_text)[:k]]
    try:
        embeddings = get_embedding_model(model_settings)
        store = get_vector_store(
            user_id, doc_type, embeddings, provider=get_embedding_provider(model_settings)
        )
        return store.similarity_search(query, k=k)
    except Exception as exc:
        logger.warning("Vector retrieval failed for %s/%s: %s", user_id, doc_type, exc)
        if doc_type == "resume":
            from app.core.sync_db import fetch_user_profile_text

            profile_text = fetch_user_profile_text(user_id)
            if profile_text:
                return [
                    Document(
                        page_content=profile_text,
                        metadata={
                            "fallback": "raw_resume",
                            "rag_unavailable": True,
                            "doc_type": doc_type,
                        },
                    )
                ]
        return []
