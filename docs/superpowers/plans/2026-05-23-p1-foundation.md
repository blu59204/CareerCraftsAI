# P1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold monorepo, wire Docker Compose, Supabase schema, Clerk auth, model router, and FastAPI app so all subsequent phases have a stable base.

**Architecture:** Monorepo with `frontend/` (Next.js 14), `backend/` (FastAPI), `worker/` (BullMQ), `supabase/` (migrations). Backend uses pydantic-settings for config, AES-256 for API key encryption, SQLAlchemy 2.0 async for ORM, Clerk JWT verified per-request via FastAPI dependency.

**Tech Stack:** Python 3.12, FastAPI 0.111+, SQLAlchemy 2.0, pydantic-settings 2.x, Next.js 14 App Router, TypeScript, Clerk, Supabase, Docker Compose, GitHub Actions

---

## File Map

| File | Responsibility |
|---|---|
| `.env.example` | Documents all required env vars |
| `docker-compose.yml` | Production service definitions |
| `docker-compose.dev.yml` | Dev overrides (hot reload, volume mounts) |
| `Makefile` | Convenience targets |
| `backend/pyproject.toml` | Python tooling config (ruff, black, pytest) |
| `backend/requirements.txt` | Pinned dependencies |
| `backend/app/main.py` | FastAPI app factory, routers, middleware |
| `backend/app/core/config.py` | pydantic-settings, all env vars typed |
| `backend/app/core/security.py` | AES-256 encrypt/decrypt, PBKDF2 key derivation |
| `backend/app/core/database.py` | Async SQLAlchemy engine + session factory |
| `backend/app/core/model_router.py` | BYOK model resolver → BaseChatModel |
| `backend/app/models/db.py` | SQLAlchemy table definitions (all PRD tables) |
| `backend/app/models/schemas.py` | Pydantic request/response schemas |
| `backend/app/api/v1/deps.py` | FastAPI dependencies: get_db, get_current_user, get_llm |
| `backend/app/api/v1/users.py` | User + model settings endpoints |
| `backend/tests/conftest.py` | Shared pytest fixtures |
| `backend/tests/unit/test_security.py` | AES-256 round-trip tests |
| `backend/tests/unit/test_model_router.py` | Router dispatch tests (mocked LLMs) |
| `frontend/package.json` | Frontend dependencies |
| `frontend/src/app/layout.tsx` | Root layout with ClerkProvider |
| `frontend/src/app/(auth)/login/page.tsx` | Login page |
| `frontend/src/app/dashboard/page.tsx` | Dashboard stub |
| `frontend/src/lib/auth.ts` | Clerk server helpers |
| `frontend/src/lib/api.ts` | Axios instance + TanStack Query client |
| `supabase/migrations/000N_*.sql` | All 7 schema migrations |
| `nginx/nginx.conf` | Reverse proxy config |
| `.github/workflows/ci.yml` | CI: lint + unit tests |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR checklist |

---

## Task 1: Repo Scaffold + Git Setup

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `.env.example`
- Create: `Makefile`

- [ ] **Step 1: Initialize git repo and create root structure**

```bash
cd "/mnt/d/CareerCraft AI"
git init
mkdir -p frontend/src/{app,components,lib,store} backend/app/{api/v1,agents,core,models,services} backend/tests/{unit,integration} worker/src/{queues,processors} supabase/migrations nginx .github/workflows docs/superpowers/plans docs/adr docs/runbooks
```

- [ ] **Step 2: Create .gitignore**

```bash
cat > .gitignore << 'EOF'
# Environment
.env
.env.local
.env.production

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.egg-info/
.pytest_cache/
.ruff_cache/
htmlcov/
.coverage

# Node
node_modules/
.next/
dist/
.turbo/

# Docker
*.log

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp

# Supabase
supabase/.branches
supabase/.temp
EOF
```

- [ ] **Step 3: Create .env.example**

```bash
cat > .env.example << 'EOF'
# === App ===
APP_SECRET_KEY=change-me-32-chars-minimum-random
APP_ENV=development
FRONTEND_URL=http://localhost:3000

# === Supabase ===
DATABASE_URL=postgresql+asyncpg://postgres:[password]@db.[project].supabase.co:5432/postgres
SUPABASE_URL=https://[project].supabase.co
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=

# === Clerk ===
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/login
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/register
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard

# === Redis ===
REDIS_URL=redis://localhost:6379

# === PinchTab ===
PINCHTAB_URL=http://localhost:9867

# === Backend ===
BACKEND_URL=http://localhost:8000

# === External APIs (optional — users supply their own) ===
# EXA_API_KEY=
# RESEND_API_KEY=
EOF
```

- [ ] **Step 4: Create Makefile**

```makefile
.PHONY: dev test lint build clean

dev:
	docker compose -f docker-compose.dev.yml up --build

test:
	cd backend && pytest tests/unit -v

test-integration:
	cd backend && INTEGRATION=1 pytest tests/integration -v

lint:
	cd backend && ruff check . && black --check .
	cd frontend && npm run lint

format:
	cd backend && ruff check --fix . && black .
	cd frontend && npm run lint -- --fix

build:
	docker compose build

clean:
	docker compose down -v
	find . -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
```

- [ ] **Step 5: Create README.md**

```markdown
# JobAgent AI

Multi-agent job search automation platform. Users bring their own AI API keys.

## Quick Start

```bash
cp .env.example .env
# Fill in .env values
make dev
```

Frontend: http://localhost:3000  
Backend API docs: http://localhost:8000/docs

## Development

```bash
make test       # unit tests
make lint       # lint check
make format     # auto-format
```

See `docs/` for architecture decisions and implementation plans.
```

- [ ] **Step 6: Initial commit**

```bash
git add .gitignore README.md .env.example Makefile
git commit -m "chore: initialize monorepo with project scaffold"
```

---

## Task 2: Backend Python Setup

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "jobagent-backend"
version = "0.1.0"
requires-python = ">=3.12"

[tool.ruff]
target-version = "py312"
line-length = 100
select = ["E", "W", "F", "I", "B", "C4", "UP", "S"]
ignore = ["S101"]  # allow assert in tests

[tool.ruff.per-file-ignores]
"tests/**" = ["S", "B"]

[tool.black]
line-length = 100
target-version = ["py312"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
filterwarnings = ["ignore::DeprecationWarning"]

[tool.coverage.run]
source = ["app"]
omit = ["tests/*"]
```

- [ ] **Step 2: Create requirements.txt**

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic==2.7.1
pydantic-settings==2.2.1
sqlalchemy[asyncio]==2.0.30
asyncpg==0.29.0
alembic==1.13.1
langchain==0.3.0
langchain-core==0.3.0
langchain-anthropic==0.3.0
langchain-openai==0.3.0
langchain-google-genai==0.3.0
langchain-ollama==0.3.0
langgraph==0.2.0
cryptography==42.0.5
clerk-backend-api==1.0.0
slowapi==0.1.9
python-multipart==0.0.9
httpx==0.27.0
redis==5.0.4
pytest==8.2.0
pytest-asyncio==0.23.6
pytest-mock==3.14.0
httpx==0.27.0
bandit==1.7.8
ruff==0.4.4
black==24.4.2
coverage==7.5.1
```

- [ ] **Step 3: Create backend/app/__init__.py**

```python
```

- [ ] **Step 4: Create required __init__.py files**

```bash
touch backend/app/api/__init__.py \
      backend/app/api/v1/__init__.py \
      backend/app/agents/__init__.py \
      backend/app/core/__init__.py \
      backend/app/models/__init__.py \
      backend/app/services/__init__.py \
      backend/tests/__init__.py \
      backend/tests/unit/__init__.py \
      backend/tests/integration/__init__.py
```

- [ ] **Step 5: Set up Python venv and install**

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "chore(backend): python project setup with pyproject.toml and requirements"
```

---

## Task 3: Config Module

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/tests/unit/test_config.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_config.py
import os
import pytest
from app.core.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-32-chars-minimum!!")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")

    settings = Settings()

    assert settings.APP_SECRET_KEY == "test-secret-key-32-chars-minimum!!"
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost/db"
    assert settings.APP_ENV == "development"


def test_settings_require_secret_key(monkeypatch):
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    with pytest.raises(Exception):
        Settings()
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd backend && source .venv/bin/activate
pytest tests/unit/test_config.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `app.core.config` does not exist yet.

- [ ] **Step 3: Implement config.py**

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_SECRET_KEY: str
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"

    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_ANON_KEY: str = ""

    CLERK_SECRET_KEY: str

    REDIS_URL: str = "redis://localhost:6379"
    PINCHTAB_URL: str = "http://localhost:9867"


settings = Settings()
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/unit/test_config.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/config.py backend/tests/unit/test_config.py
git commit -m "feat(core): add pydantic-settings config module"
```

---

## Task 4: Security Module (AES-256 + PBKDF2)

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/tests/unit/test_security.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_security.py
import pytest
from app.core.security import encrypt_api_key, decrypt_api_key, derive_key


def test_encrypt_decrypt_roundtrip():
    secret = "test-secret-key-32-chars-minimum!!"
    plaintext = "sk-anthropic-key-abc123"
    encrypted = encrypt_api_key(plaintext, secret)
    assert encrypted != plaintext
    decrypted = decrypt_api_key(encrypted, secret)
    assert decrypted == plaintext


def test_encrypt_produces_different_ciphertext_each_time():
    secret = "test-secret-key-32-chars-minimum!!"
    plaintext = "sk-test-key"
    enc1 = encrypt_api_key(plaintext, secret)
    enc2 = encrypt_api_key(plaintext, secret)
    assert enc1 != enc2  # different IV each time


def test_decrypt_wrong_key_raises():
    secret = "test-secret-key-32-chars-minimum!!"
    wrong = "wrong-secret-key-32-chars-minimum!"
    encrypted = encrypt_api_key("my-api-key", secret)
    with pytest.raises(Exception):
        decrypt_api_key(encrypted, wrong)


def test_derive_key_deterministic():
    key1 = derive_key("password", b"salt1234")
    key2 = derive_key("password", b"salt1234")
    assert key1 == key2


def test_derive_key_different_salts_differ():
    key1 = derive_key("password", b"salt1234")
    key2 = derive_key("password", b"salt5678")
    assert key1 != key2
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_security.py -v
```

Expected: ImportError — `app.core.security` not defined.

- [ ] **Step 3: Implement security.py**

```python
# backend/app/core/security.py
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


def derive_key(secret: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(secret.encode())


def encrypt_api_key(plaintext: str, app_secret: str) -> str:
    salt = os.urandom(16)
    key = derive_key(app_secret, salt)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    payload = salt + nonce + ciphertext
    return base64.b64encode(payload).decode()


def decrypt_api_key(encrypted: str, app_secret: str) -> str:
    payload = base64.b64decode(encrypted.encode())
    salt = payload[:16]
    nonce = payload[16:28]
    ciphertext = payload[28:]
    key = derive_key(app_secret, salt)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode()
```

- [ ] **Step 4: Run — verify passes**

```bash
pytest tests/unit/test_security.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/unit/test_security.py
git commit -m "feat(core): AES-256-GCM API key encryption with PBKDF2 key derivation"
```

---

## Task 5: Database Client

**Files:**
- Create: `backend/app/core/database.py`

- [ ] **Step 1: Implement database.py**

```python
# backend/app/core/database.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/database.py
git commit -m "feat(core): async SQLAlchemy engine and session factory"
```

---

## Task 6: SQLAlchemy Models

**Files:**
- Create: `backend/app/models/db.py`
- Create: `backend/app/models/schemas.py`

- [ ] **Step 1: Implement db.py (all PRD tables)**

```python
# backend/app/models/db.py
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String)
    avatar_url: Mapped[str | None] = mapped_column(String)
    google_id: Mapped[str | None] = mapped_column(String, unique=True)
    clerk_id: Mapped[str | None] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    model_settings: Mapped[list["UserModelSettings"]] = relationship(back_populates="user")
    documents: Mapped[list["UserDocument"]] = relationship(back_populates="user")
    applications: Mapped[list["JobApplication"]] = relationship(back_populates="user")
    leads: Mapped[list["Lead"]] = relationship(back_populates="user")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="user")


class UserModelSettings(Base):
    __tablename__ = "user_model_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String, nullable=False)
    api_key_enc: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String)
    ollama_url: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="model_settings")


class UserDocument(Base):
    __tablename__ = "user_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    doc_type: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="documents")


class JobApplication(Base):
    __tablename__ = "job_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    company: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    job_url: Mapped[str | None] = mapped_column(String)
    jd_text: Mapped[str | None] = mapped_column(Text)
    match_score: Mapped[int | None] = mapped_column(Integer)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_documents.id"))
    cover_letter: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="saved")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    followup_day5: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    followup_day12: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="applications")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    company: Mapped[str | None] = mapped_column(String)
    linkedin_url: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="cold")
    last_contact: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="leads")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    agent_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="running")
    input: Mapped[dict | None] = mapped_column(JSONB)
    output: Mapped[dict | None] = mapped_column(JSONB)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="agent_runs")
```

- [ ] **Step 2: Implement schemas.py**

```python
# backend/app/models/schemas.py
import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str | None = None
    clerk_id: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    avatar_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelSettingsCreate(BaseModel):
    provider: Literal["anthropic", "openai", "google", "ollama", "nvidia_nim"]
    api_key: str  # plaintext — encrypted before storage
    model_name: str
    ollama_url: str | None = None


class ModelSettingsResponse(BaseModel):
    id: uuid.UUID
    provider: str
    model_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/
git commit -m "feat(models): SQLAlchemy ORM models for all PRD tables + Pydantic schemas"
```

---

## Task 7: Model Router

**Files:**
- Create: `backend/app/core/model_router.py`
- Create: `backend/tests/unit/test_model_router.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_model_router.py
import uuid
import pytest
from unittest.mock import MagicMock, patch
from app.core.model_router import get_llm
from app.models.db import UserModelSettings


def make_settings(provider: str, model_name: str = "test-model", ollama_url: str | None = None):
    s = MagicMock(spec=UserModelSettings)
    s.provider = provider
    s.model_name = model_name
    s.api_key_enc = "encrypted-key"
    s.ollama_url = ollama_url
    return s


@pytest.fixture
def mock_db_with_settings(mock_settings):
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = mock_settings
    return db


@pytest.mark.parametrize("provider,expected_class_path", [
    ("anthropic", "langchain_anthropic.ChatAnthropic"),
    ("openai", "langchain_openai.ChatOpenAI"),
    ("google", "langchain_google_genai.ChatGoogleGenerativeAI"),
    ("ollama", "langchain_ollama.ChatOllama"),
    ("nvidia_nim", "langchain_openai.ChatOpenAI"),
])
def test_model_router_dispatches_correct_class(provider, expected_class_path):
    settings = make_settings(provider, ollama_url="http://localhost:11434" if provider == "ollama" else None)
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = settings

    module, cls = expected_class_path.rsplit(".", 1)
    with patch(f"{module}.{cls}") as mock_cls, \
         patch("app.core.model_router.decrypt_api_key", return_value="plaintext-key"), \
         patch("app.core.model_router.settings") as mock_app_settings:
        mock_app_settings.APP_SECRET_KEY = "secret"
        mock_cls.return_value = MagicMock()
        result = get_llm(str(uuid.uuid4()), db)
        mock_cls.assert_called_once()


def test_model_router_raises_when_no_settings():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        get_llm(str(uuid.uuid4()), db)
    assert exc.value.status_code == 400


def test_model_router_raises_on_unknown_provider():
    s = make_settings("unknown_provider")
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = s
    with patch("app.core.model_router.decrypt_api_key", return_value="key"), \
         patch("app.core.model_router.settings") as mock_app_settings:
        mock_app_settings.APP_SECRET_KEY = "secret"
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            get_llm(str(uuid.uuid4()), db)
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_model_router.py -v
```

Expected: ImportError — `app.core.model_router` not defined.

- [ ] **Step 3: Implement model_router.py**

```python
# backend/app/core/model_router.py
from fastapi import HTTPException
from langchain_core.language_models import BaseChatModel
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from app.core.security import decrypt_api_key
from app.core.config import settings
from app.models.db import UserModelSettings


def get_llm(user_id: str, db) -> BaseChatModel:
    model_settings: UserModelSettings | None = (
        db.query(UserModelSettings)
        .filter_by(user_id=user_id, is_active=True)
        .first()
    )
    if not model_settings:
        raise HTTPException(status_code=400, detail="No active model configured. Add a model in Settings.")

    api_key = decrypt_api_key(model_settings.api_key_enc, settings.APP_SECRET_KEY)

    match model_settings.provider:
        case "anthropic":
            return ChatAnthropic(model=model_settings.model_name, api_key=api_key)
        case "openai":
            return ChatOpenAI(model=model_settings.model_name, api_key=api_key)
        case "google":
            return ChatGoogleGenerativeAI(model=model_settings.model_name, google_api_key=api_key)
        case "ollama":
            return ChatOllama(model=model_settings.model_name, base_url=model_settings.ollama_url)
        case "nvidia_nim":
            return ChatOpenAI(
                model=model_settings.model_name,
                api_key=api_key,
                base_url="https://integrate.api.nvidia.com/v1",
            )
        case _:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {model_settings.provider}")
```

- [ ] **Step 4: Run — verify passes**

```bash
pytest tests/unit/test_model_router.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/model_router.py backend/tests/unit/test_model_router.py
git commit -m "feat(core): BYOK model router for all 5 providers (Anthropic/OpenAI/Google/Ollama/NVIDIA NIM)"
```

---

## Task 8: FastAPI App + Dependencies

**Files:**
- Create: `backend/app/api/v1/deps.py`
- Create: `backend/app/api/v1/users.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Create deps.py (FastAPI dependency injection)**

```python
# backend/app/api/v1/deps.py
from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from clerk_backend_api import Clerk
from app.core.config import settings
from app.core.database import get_db
from app.models.db import User


async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization[7:]
    clerk = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)

    try:
        claims = clerk.verify_token(token)
        clerk_id = claims.sub
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    from sqlalchemy import select
    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user
```

- [ ] **Step 2: Create users.py**

```python
# backend/app/api/v1/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.v1.deps import get_current_user, get_db
from app.core.security import encrypt_api_key
from app.core.config import settings
from app.models.db import User, UserModelSettings
from app.models.schemas import (
    UserCreate, UserResponse,
    ModelSettingsCreate, ModelSettingsResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.clerk_id == payload.clerk_id))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    user = User(**payload.model_dump())
    db.add(user)
    await db.flush()
    return user


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/me/models", response_model=ModelSettingsResponse, status_code=201)
async def add_model_settings(
    payload: ModelSettingsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    encrypted_key = encrypt_api_key(payload.api_key, settings.APP_SECRET_KEY)
    model_setting = UserModelSettings(
        user_id=current_user.id,
        provider=payload.provider,
        api_key_enc=encrypted_key,
        model_name=payload.model_name,
        ollama_url=payload.ollama_url,
        is_active=True,
    )
    db.add(model_setting)
    await db.flush()
    return model_setting


@router.get("/me/models", response_model=list[ModelSettingsResponse])
async def list_model_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserModelSettings).where(UserModelSettings.user_id == current_user.id)
    )
    return result.scalars().all()
```

- [ ] **Step 3: Create main.py**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.api.v1 import users

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="JobAgent AI API",
    version="0.1.0",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Create conftest.py**

```python
# backend/tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.language_models.fake_chat_models import FakeChatModel


@pytest.fixture
def mock_llm():
    return FakeChatModel(responses=["mocked LLM response"])


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = "00000000-0000-0000-0000-000000000001"
    user.email = "test@example.com"
    user.clerk_id = "user_test123"
    return user
```

- [ ] **Step 5: Verify app starts**

```bash
cd backend && source .venv/bin/activate
# Set minimal env vars for startup test
export APP_SECRET_KEY="test-secret-key-32-chars-minimum!!" \
       DATABASE_URL="postgresql+asyncpg://x:x@localhost/x" \
       SUPABASE_URL="https://x.supabase.co" \
       SUPABASE_SERVICE_KEY="x" \
       CLERK_SECRET_KEY="sk_test_x" \
       REDIS_URL="redis://localhost:6379"
python -c "from app.main import app; print('App imports OK')"
```

Expected: `App imports OK`

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/api/ backend/tests/conftest.py
git commit -m "feat(api): FastAPI app factory, deps injection, users + model settings endpoints"
```

---

## Task 9: Supabase Migrations

**Files:**
- Create: `supabase/migrations/0001_create_users.sql` through `0007_create_pgvector_indexes.sql`

- [ ] **Step 1: Create migration 0001 — users**

```sql
-- supabase/migrations/0001_create_users.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  full_name TEXT,
  avatar_url TEXT,
  google_id TEXT UNIQUE,
  clerk_id TEXT UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

- [ ] **Step 2: Create migration 0002 — model settings**

```sql
-- supabase/migrations/0002_create_model_settings.sql
CREATE TABLE user_model_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  api_key_enc TEXT,
  model_name TEXT,
  ollama_url TEXT,
  is_active BOOLEAN DEFAULT true
);

CREATE INDEX idx_model_settings_user_id ON user_model_settings(user_id);
```

- [ ] **Step 3: Create migration 0003 — documents**

```sql
-- supabase/migrations/0003_create_documents.sql
CREATE TABLE user_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  doc_type TEXT NOT NULL,
  filename TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  raw_text TEXT,
  embedded_at TIMESTAMPTZ,
  is_primary BOOLEAN DEFAULT false
);

CREATE INDEX idx_documents_user_id ON user_documents(user_id);
CREATE INDEX idx_documents_doc_type ON user_documents(user_id, doc_type);
```

- [ ] **Step 4: Create migration 0004 — job applications**

```sql
-- supabase/migrations/0004_create_applications.sql
CREATE TABLE job_applications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  company TEXT NOT NULL,
  role TEXT NOT NULL,
  job_url TEXT,
  jd_text TEXT,
  match_score INTEGER CHECK (match_score BETWEEN 0 AND 100),
  resume_id UUID REFERENCES user_documents(id),
  cover_letter TEXT,
  status TEXT DEFAULT 'saved'
    CHECK (status IN ('saved','applied','viewed','interview','offer','rejected')),
  applied_at TIMESTAMPTZ,
  followup_day5 TIMESTAMPTZ,
  followup_day12 TIMESTAMPTZ,
  notes TEXT
);

CREATE INDEX idx_applications_user_id ON job_applications(user_id);
CREATE INDEX idx_applications_status ON job_applications(user_id, status);
```

- [ ] **Step 5: Create migrations 0005–0007**

```sql
-- supabase/migrations/0005_create_leads.sql
CREATE TABLE leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  name TEXT,
  email TEXT,
  company TEXT,
  linkedin_url TEXT,
  status TEXT DEFAULT 'cold' CHECK (status IN ('cold','warm','replied','converted')),
  last_contact TIMESTAMPTZ,
  notes TEXT
);
CREATE INDEX idx_leads_user_id ON leads(user_id);
```

```sql
-- supabase/migrations/0006_create_agent_runs.sql
CREATE TABLE agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  agent_type TEXT NOT NULL,
  status TEXT DEFAULT 'running'
    CHECK (status IN ('running','awaiting_approval','completed','failed')),
  input JSONB,
  output JSONB,
  tokens_used INTEGER,
  duration_ms INTEGER,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);
CREATE INDEX idx_agent_runs_user_id ON agent_runs(user_id);
CREATE INDEX idx_agent_runs_status ON agent_runs(status);
```

```sql
-- supabase/migrations/0007_create_pgvector_indexes.sql
CREATE EXTENSION IF NOT EXISTS vector;

-- LangChain PGVector manages its own tables (langchain_pg_collection, langchain_pg_embedding)
-- This migration adds HNSW indexes after LangChain creates the tables on first use.
-- Run this after first RAG ingestion in production:
--
-- CREATE INDEX CONCURRENTLY ON langchain_pg_embedding
--   USING hnsw (embedding vector_cosine_ops)
--   WITH (m = 16, ef_construction = 64);
--
-- Placeholder for the index — created post-ingestion to avoid schema chicken-and-egg.
SELECT 1;
```

- [ ] **Step 6: Commit**

```bash
git add supabase/
git commit -m "feat(db): Supabase migrations for all PRD tables + pgvector extension"
```

---

## Task 10: Next.js Frontend Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/src/app/layout.tsx`
- Create: `frontend/src/app/(auth)/login/page.tsx`
- Create: `frontend/src/app/dashboard/page.tsx`
- Create: `frontend/src/lib/auth.ts`
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 1: Create Next.js app**

```bash
cd frontend
npx create-next-app@14 . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --no-git
```

When prompted, answer:
- Would you like to use Turbopack? → No

- [ ] **Step 2: Install dependencies**

```bash
npm install \
  @clerk/nextjs \
  @tanstack/react-query@5 \
  @tanstack/react-query-devtools@5 \
  zustand \
  axios \
  sonner

npx shadcn-ui@latest init
```

shadcn init choices: Default style, Slate base color, CSS variables yes.

```bash
npx shadcn-ui@latest add button card dialog input label badge separator tabs scroll-area select textarea
```

- [ ] **Step 3: Create frontend/.env.local**

```bash
cat > .env.local << 'EOF'
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_replace_me
CLERK_SECRET_KEY=sk_test_replace_me
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/login
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/register
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF
```

- [ ] **Step 4: Create root layout with ClerkProvider**

```tsx
// frontend/src/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { Providers } from "@/components/layout/Providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "JobAgent AI",
  description: "Automate your job search with AI agents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className={inter.className}>
          <Providers>{children}</Providers>
        </body>
      </html>
    </ClerkProvider>
  );
}
```

- [ ] **Step 5: Create Providers component (TanStack Query)**

```tsx
// frontend/src/components/layout/Providers.tsx
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState } from "react";
import { Toaster } from "sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 60_000 } },
  }));

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster position="top-right" />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

- [ ] **Step 6: Create auth pages**

```tsx
// frontend/src/app/(auth)/login/page.tsx
import { SignIn } from "@clerk/nextjs";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50">
      <SignIn />
    </main>
  );
}
```

```tsx
// frontend/src/app/(auth)/register/page.tsx
import { SignUp } from "@clerk/nextjs";

export default function RegisterPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50">
      <SignUp />
    </main>
  );
}
```

- [ ] **Step 7: Create middleware for Clerk route protection**

```typescript
// frontend/src/middleware.ts
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher(["/login(.*)", "/register(.*)", "/api/webhooks(.*)"]);

export default clerkMiddleware((auth, req) => {
  if (!isPublicRoute(req)) auth().protect();
});

export const config = {
  matcher: ["/((?!.*\\..*|_next).*)", "/", "/(api|trpc)(.*)"],
};
```

- [ ] **Step 8: Create API client**

```typescript
// frontend/src/lib/api.ts
import axios from "axios";

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use(async (config) => {
  // Clerk token injected by each request — imported dynamically to avoid SSR issues
  if (typeof window !== "undefined") {
    const { getToken } = await import("@clerk/nextjs/client" as any).catch(() => ({ getToken: null }));
    if (getToken) {
      const token = await getToken();
      if (token) config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});
```

- [ ] **Step 9: Create dashboard stub**

```tsx
// frontend/src/app/dashboard/page.tsx
import { currentUser } from "@clerk/nextjs/server";

export default async function DashboardPage() {
  const user = await currentUser();
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Welcome, {user?.firstName ?? "there"}</h1>
      <p className="text-slate-500 mt-2">Your job search dashboard. Agents ready.</p>
    </main>
  );
}
```

- [ ] **Step 10: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 11: Commit**

```bash
cd ..
git add frontend/
git commit -m "feat(frontend): Next.js 14 scaffold with Clerk auth, TanStack Query, shadcn/ui"
```

---

## Task 11: Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `docker-compose.dev.yml`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `worker/Dockerfile`
- Create: `nginx/nginx.conf`

- [ ] **Step 1: Create backend Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create frontend Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
CMD ["node", "server.js"]
```

- [ ] **Step 3: Create nginx.conf**

```nginx
# nginx/nginx.conf
events { worker_connections 1024; }

http {
  upstream frontend { server frontend:3000; }
  upstream backend  { server backend:8000; }

  server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
  }

  server {
    listen 443 ssl;
    server_name _;

    ssl_certificate     /etc/letsencrypt/live/yourdomain/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain/privkey.pem;

    location /api/ {
      proxy_pass http://backend;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
      proxy_pass http://frontend;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
    }
  }
}
```

- [ ] **Step 4: Create docker-compose.yml (production)**

```yaml
# docker-compose.yml
version: "3.9"

services:
  frontend:
    build: ./frontend
    env_file: .env
    depends_on: [backend]
    restart: unless-stopped

  backend:
    build: ./backend
    env_file: .env
    depends_on: [redis]
    restart: unless-stopped

  worker:
    build: ./worker
    env_file: .env
    depends_on: [redis]
    restart: unless-stopped

  pinchtab:
    image: ghcr.io/pinchtab/pinchtab:0.7.6
    ports: ["9867:9867"]
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes: [redis_data:/data]
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on: [frontend, backend]
    restart: unless-stopped

volumes:
  redis_data:
```

- [ ] **Step 5: Create docker-compose.dev.yml**

```yaml
# docker-compose.dev.yml
version: "3.9"

services:
  frontend:
    build:
      context: ./frontend
      target: builder
    command: npm run dev
    volumes: [./frontend/src:/app/src]
    ports: ["3000:3000"]
    env_file: .env

  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes: [./backend/app:/app/app]
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [redis]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  pinchtab:
    image: ghcr.io/pinchtab/pinchtab:0.7.6
    ports: ["9867:9867"]
```

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml docker-compose.dev.yml backend/Dockerfile frontend/Dockerfile nginx/
git commit -m "chore(docker): production and dev Docker Compose with all services"
```

---

## Task 12: CI/CD Pipeline

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`

- [ ] **Step 1: Create CI workflow**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  backend-lint-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - run: pip install -r requirements.txt

      - name: Lint (ruff)
        run: ruff check .

      - name: Format check (black)
        run: black --check .

      - name: Security scan (bandit)
        run: bandit -r app/ -ll -x tests/

      - name: Unit tests
        run: pytest tests/unit -v --cov=app --cov-report=term-missing
        env:
          APP_SECRET_KEY: "test-secret-key-32-chars-minimum!!"
          DATABASE_URL: "postgresql+asyncpg://x:x@localhost/x"
          SUPABASE_URL: "https://x.supabase.co"
          SUPABASE_SERVICE_KEY: "x"
          CLERK_SECRET_KEY: "sk_test_x"
          REDIS_URL: "redis://localhost:6379"

  frontend-lint-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - run: npm ci

      - name: Lint
        run: npm run lint

      - name: Type check
        run: npx tsc --noEmit

      - name: Security audit
        run: npm audit --audit-level=high
```

- [ ] **Step 2: Create PR template**

```markdown
<!-- .github/PULL_REQUEST_TEMPLATE.md -->
## What

<!-- One-sentence description of the change -->

## Why

<!-- Why this change is needed -->

## Test Coverage

- [ ] Unit tests added/updated
- [ ] Integration tests updated (if behavior change)
- [ ] Manually tested the happy path

## Security Checklist

- [ ] No API keys or secrets in code
- [ ] User input validated at boundaries
- [ ] No raw SQL string construction
- [ ] Bandit passes locally: `cd backend && bandit -r app/ -ll`

## Screenshots (UI changes only)

<!-- Attach before/after screenshots -->
```

- [ ] **Step 3: Commit**

```bash
git add .github/
git commit -m "ci: GitHub Actions CI pipeline with lint, tests, Bandit, npm audit"
```

---

## Task 13: Run Full Test Suite + Verify P1 Complete

- [ ] **Step 1: Run all unit tests**

```bash
cd backend && source .venv/bin/activate
APP_SECRET_KEY="test-secret-key-32-chars-minimum!!" \
DATABASE_URL="postgresql+asyncpg://x:x@localhost/x" \
SUPABASE_URL="https://x.supabase.co" \
SUPABASE_SERVICE_KEY="x" \
CLERK_SECRET_KEY="sk_test_x" \
REDIS_URL="redis://localhost:6379" \
pytest tests/unit -v
```

Expected: All tests pass (config, security, model_router).

- [ ] **Step 2: Run linter**

```bash
ruff check . && black --check .
```

Expected: No errors.

- [ ] **Step 3: Run Bandit**

```bash
bandit -r app/ -ll
```

Expected: No HIGH severity issues.

- [ ] **Step 4: Verify frontend**

```bash
cd ../frontend && npm run lint && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 5: Final P1 commit**

```bash
cd ..
git add -A
git commit -m "chore(p1): Phase 1 foundation complete — all tests passing, CI green"
```

**P1 done. Proceed to P2 (RAG Pipeline).**
