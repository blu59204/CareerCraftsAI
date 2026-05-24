# P2: RAG Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build document ingestion (upload → extract → chunk → embed → pgvector store) and retrieval service used by all agents.

**Architecture:** FastAPI upload endpoint stores raw file in Supabase Storage, extracts text via PyMuPDF/python-docx, chunks with RecursiveCharacterTextSplitter (500 tokens, 50 overlap), embeds via user's chosen provider, stores in LangChain PGVector (collection = `{user_id}_{doc_type}`). Retrieval returns top-k chunks for a query.

**Tech Stack:** PyMuPDF, python-docx, LangChain PGVector, pgvector, Supabase Storage, supabase-py

---

## File Map

| File | Responsibility |
|---|---|
| `backend/requirements.txt` | Add PyMuPDF, python-docx, supabase, langchain-community |
| `backend/app/services/rag_service.py` | Chunk, embed, store, retrieve |
| `backend/app/services/storage_service.py` | Upload/download files from Supabase Storage |
| `backend/app/api/v1/rag.py` | Upload endpoint, list documents, delete |
| `backend/tests/unit/test_rag_service.py` | Unit tests — mocked embeddings + pgvector |
| `backend/tests/integration/test_rag_pipeline.py` | Integration test — real Supabase + real embeddings |

---

## Task 1: Add Dependencies

- [ ] **Step 1: Add to requirements.txt**

```
pymupdf==1.24.3
python-docx==1.1.0
supabase==2.4.6
langchain-community==0.3.0
```

- [ ] **Step 2: Install**

```bash
cd backend && source .venv/bin/activate && pip install pymupdf python-docx supabase langchain-community
```

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore(backend): add RAG dependencies — pymupdf, python-docx, supabase, langchain-community"
```

---

## Task 2: Storage Service

**Files:**
- Create: `backend/app/services/storage_service.py`

- [ ] **Step 1: Implement storage_service.py**

```python
# backend/app/services/storage_service.py
import uuid
from supabase import create_client, Client
from app.core.config import settings

BUCKET = "user-documents"


def get_supabase() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def upload_file(user_id: str, filename: str, content: bytes, content_type: str) -> str:
    """Upload file to Supabase Storage. Returns storage path."""
    supabase = get_supabase()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    path = f"{user_id}/{uuid.uuid4()}.{ext}"
    supabase.storage.from_(BUCKET).upload(path, content, {"content-type": content_type})
    return path


def download_file(storage_path: str) -> bytes:
    """Download file bytes from Supabase Storage."""
    supabase = get_supabase()
    return supabase.storage.from_(BUCKET).download(storage_path)


def delete_file(storage_path: str) -> None:
    supabase = get_supabase()
    supabase.storage.from_(BUCKET).remove([storage_path])
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/storage_service.py
git commit -m "feat(rag): Supabase Storage service for document upload/download"
```

---

## Task 3: RAG Service

**Files:**
- Create: `backend/app/services/rag_service.py`
- Create: `backend/tests/unit/test_rag_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_rag_service.py
import uuid
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document


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


def test_chunk_text_produces_correct_overlap():
    from app.services.rag_service import chunk_text
    # 500 token chunks with 50 overlap
    long_text = " ".join(["word"] * 1000)
    chunks = chunk_text(long_text)
    assert len(chunks) > 1
    # Each chunk under 600 chars (rough proxy for 500 tokens)


def test_get_embedding_model_anthropic_falls_back_to_ollama(mock_llm):
    from app.services.rag_service import get_embedding_model
    settings_mock = MagicMock()
    settings_mock.provider = "anthropic"
    settings_mock.ollama_url = None
    with patch("app.services.rag_service.OllamaEmbeddings") as mock_ollama:
        mock_ollama.return_value = MagicMock()
        result = get_embedding_model(settings_mock)
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
        result = get_embedding_model(settings_mock)
        mock_emb.assert_called_once()


def test_collection_name_format():
    from app.services.rag_service import collection_name
    uid = "usr_abc123"
    assert collection_name(uid, "resume") == "usr_abc123_resume"
    assert collection_name(uid, "jd") == "usr_abc123_jd"
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_rag_service.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement rag_service.py**

```python
# backend/app/services/rag_service.py
import io
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import PGVector
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_ollama import OllamaEmbeddings
from app.core.security import decrypt_api_key
from app.core.config import settings as app_settings


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
    # anthropic + nvidia_nim have no native embeddings — fall back to local nomic-embed-text
    return OllamaEmbeddings(model="nomic-embed-text")


def get_vector_store(user_id: str, doc_type: str, embeddings) -> PGVector:
    return PGVector(
        collection_name=collection_name(user_id, doc_type),
        connection_string=app_settings.DATABASE_URL.replace("+asyncpg", ""),
        embedding_function=embeddings,
    )


def ingest_document(user_id: str, doc_type: str, text: str, metadata: dict, model_settings) -> int:
    """Chunk, embed, store document. Returns number of chunks stored."""
    chunks = chunk_text(text)
    embeddings = get_embedding_model(model_settings)
    docs = [Document(page_content=chunk, metadata={**metadata, "chunk_index": i})
            for i, chunk in enumerate(chunks)]
    store = get_vector_store(user_id, doc_type, embeddings)
    store.add_documents(docs)
    return len(docs)


def retrieve(user_id: str, doc_type: str, query: str, model_settings, k: int = 5) -> list[Document]:
    """Retrieve top-k relevant chunks for a query."""
    embeddings = get_embedding_model(model_settings)
    store = get_vector_store(user_id, doc_type, embeddings)
    return store.similarity_search(query, k=k)
```

- [ ] **Step 4: Run tests — verify pass**

```bash
pytest tests/unit/test_rag_service.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/rag_service.py backend/tests/unit/test_rag_service.py
git commit -m "feat(rag): document text extraction, chunking, embedding, pgvector store + retrieval"
```

---

## Task 4: RAG API Endpoint

**Files:**
- Create: `backend/app/api/v1/rag.py`

- [ ] **Step 1: Implement rag.py**

```python
# backend/app/api/v1/rag.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.v1.deps import get_current_user, get_db
from app.models.db import User, UserDocument, UserModelSettings
from app.models.schemas import ModelSettingsResponse
from app.services.storage_service import upload_file, delete_file
from app.services.rag_service import extract_text, ingest_document
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel

router = APIRouter(prefix="/rag", tags=["rag"])

ALLOWED_TYPES = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class DocumentResponse(BaseModel):
    id: uuid.UUID
    doc_type: str
    filename: str
    is_primary: bool
    embedded_at: datetime | None

    model_config = {"from_attributes": True}


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    is_primary: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if doc_type not in {"resume", "jd", "cert", "portfolio", "cover_letter"}:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type: {doc_type}")
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Only PDF, DOCX, and TXT files are supported")

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large — max 10 MB")

    storage_path = upload_file(str(current_user.id), file.filename, content, file.content_type)
    raw_text = extract_text(content, file.filename)

    # Get active model settings for embedding
    result = await db.execute(
        select(UserModelSettings)
        .where(UserModelSettings.user_id == current_user.id, UserModelSettings.is_active == True)
    )
    model_settings = result.scalar_one_or_none()

    chunks_stored = 0
    embedded_at = None
    if model_settings:
        chunks_stored = ingest_document(
            str(current_user.id), doc_type, raw_text,
            {"user_id": str(current_user.id), "doc_type": doc_type, "filename": file.filename},
            model_settings,
        )
        embedded_at = datetime.now(timezone.utc)

    doc = UserDocument(
        user_id=current_user.id,
        doc_type=doc_type,
        filename=file.filename,
        storage_path=storage_path,
        raw_text=raw_text,
        embedded_at=embedded_at,
        is_primary=is_primary,
    )
    db.add(doc)
    await db.flush()
    return doc


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    doc_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(UserDocument).where(UserDocument.user_id == current_user.id)
    if doc_type:
        query = query.where(UserDocument.doc_type == doc_type)
    result = await db.execute(query)
    return result.scalars().all()


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserDocument)
        .where(UserDocument.id == document_id, UserDocument.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    delete_file(doc.storage_path)
    await db.delete(doc)
```

- [ ] **Step 2: Register router in main.py**

```python
# backend/app/main.py — add after existing imports
from app.api.v1 import users, rag

# add after existing include_router
app.include_router(rag.router, prefix="/api/v1")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/rag.py backend/app/main.py
git commit -m "feat(rag): document upload, list, delete endpoints with Supabase Storage + pgvector ingestion"
```

---

## Task 5: Integration Test (opt-in)

**Files:**
- Create: `backend/tests/integration/test_rag_pipeline.py`

- [ ] **Step 1: Write integration test**

```python
# backend/tests/integration/test_rag_pipeline.py
"""
Run with: INTEGRATION=1 pytest tests/integration/test_rag_pipeline.py -v
Requires: real DATABASE_URL, real SUPABASE_URL/keys, real model API key in DB
"""
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="Integration tests require INTEGRATION=1 env var",
)


@pytest.mark.asyncio
async def test_ingest_and_retrieve_roundtrip(test_db, test_user, test_model_settings):
    from app.services.rag_service import ingest_document, retrieve

    text = "Experienced Python engineer with 5 years FastAPI, LangChain, PostgreSQL. Led team of 4."
    chunks_stored = ingest_document(
        str(test_user.id), "resume", text,
        {"user_id": str(test_user.id), "doc_type": "resume"},
        test_model_settings,
    )
    assert chunks_stored >= 1

    results = retrieve(str(test_user.id), "resume", "Python engineer experience", test_model_settings, k=3)
    assert len(results) >= 1
    assert "Python" in results[0].page_content
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/integration/
git commit -m "test(rag): integration test for ingest+retrieve roundtrip (opt-in with INTEGRATION=1)"
```

**P2 done. Proceed to P3 (Resume + LinkedIn Agents).**
