# JobAgent AI — System Design

**Date:** 2026-05-23  
**Status:** Approved  
**Authors:** Claude Code (architect), team  
**PRD:** `CareerCraft AI.md` v1.0  

---

## 1. Scope

Full-stack multi-agent job search automation platform. Users bring own API keys (BYOK). Agents handle resume tailoring, job search, auto-apply, LinkedIn optimization, and recruiter follow-up.

This design covers: repository structure, infrastructure topology, agent architecture, real-time streaming, model router, testing strategy, git workflow, security, and documentation standards.

**Out of scope for v1.0:** mobile app, team/multi-user workspaces, billing/metering, self-hosted Supabase.

---

## 2. Infrastructure

### 2.1 Model

**Hybrid:** Managed cloud services for DB/auth, self-hosted Docker for application logic.

| Service | Where | Notes |
|---|---|---|
| PostgreSQL 16 + pgvector 0.7+ | Supabase Cloud | Free tier, managed migrations, built-in pgvector |
| File storage (resumes, docs) | Supabase Storage | S3-compatible, same dashboard |
| Authentication + Google OAuth | Clerk Cloud | Free 10k MAU, handles Gmail scope |
| FastAPI backend + LangGraph agents | Docker on VPS | Application logic, hackable |
| Redis 7 + BullMQ 5 | Docker on VPS | Job queue + cache |
| PinchTab 0.7.6 | Docker on VPS | Browser automation for job boards |
| Nginx | Docker on VPS | SSL termination, reverse proxy |

### 2.2 Docker Compose Services

```yaml
# docker-compose.yml (production)
services:
  frontend:   # Next.js → :3000
  backend:    # FastAPI → :8000
  worker:     # Node.js BullMQ processor → internal
  pinchtab:   # PinchTab binary → :9867
  redis:      # Redis 7 → :6379
  nginx:      # → :80/:443

# Supabase is external — connection via DATABASE_URL env var
```

Dev overrides in `docker-compose.dev.yml`: hot reload for frontend and backend, volume mounts, relaxed CORS.

---

## 3. Repository Structure

Monorepo — single git repository, three application directories.

```
jobagent-ai/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml              # lint + unit tests on every PR
│   │   └── cd.yml              # deploy on merge to main
│   └── PULL_REQUEST_TEMPLATE.md
├── docs/
│   ├── superpowers/specs/      # design documents
│   └── adr/                    # Architecture Decision Records
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js 14 App Router (route groups match PRD §3.1)
│   │   │   ├── (auth)/
│   │   │   │   ├── login/
│   │   │   │   └── register/
│   │   │   ├── dashboard/
│   │   │   ├── resume/
│   │   │   │   ├── upload/
│   │   │   │   ├── builder/
│   │   │   │   ├── optimize/
│   │   │   │   └── versions/
│   │   │   ├── jobs/
│   │   │   │   ├── search/
│   │   │   │   ├── matches/
│   │   │   │   └── [id]/
│   │   │   ├── applications/
│   │   │   │   └── [id]/
│   │   │   ├── linkedin/
│   │   │   │   ├── audit/
│   │   │   │   └── optimize/
│   │   │   ├── email/
│   │   │   │   ├── inbox/
│   │   │   │   ├── compose/
│   │   │   │   └── templates/
│   │   │   ├── leads/
│   │   │   └── settings/
│   │   │       ├── models/
│   │   │       ├── gmail/
│   │   │       └── profile/
│   │   ├── components/
│   │   │   ├── ui/             # shadcn/ui primitives (Button, Dialog, Card, etc.)
│   │   │   ├── agents/
│   │   │   │   ├── AgentStatusStream.tsx   # renders SSE live log
│   │   │   │   ├── AgentRunCard.tsx
│   │   │   │   └── ApprovalModal.tsx       # human-in-loop gate UI
│   │   │   ├── resume/
│   │   │   ├── jobs/
│   │   │   └── layout/
│   │   │       ├── Sidebar.tsx
│   │   │       └── Header.tsx
│   │   ├── lib/
│   │   │   ├── api.ts          # axios instance + TanStack Query factories
│   │   │   ├── sse.ts          # useAgentStream(runId) hook
│   │   │   └── auth.ts         # Clerk helpers + server-side auth
│   │   └── store/
│   │       ├── agentSlice.ts   # Zustand: active runs, SSE state
│   │       └── userSlice.ts    # Zustand: profile, model settings
│   ├── public/
│   ├── package.json
│   ├── tailwind.config.ts
│   └── next.config.ts
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app factory, middleware, routers
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── agents.py   # /run, /stream, /approve, /cancel
│   │   │       ├── users.py
│   │   │       ├── jobs.py
│   │   │       ├── resume.py
│   │   │       ├── gmail.py
│   │   │       ├── rag.py
│   │   │       └── deps.py     # get_current_user, get_db, get_llm
│   │   ├── agents/
│   │   │   ├── state.py        # AgentState TypedDict
│   │   │   ├── orchestrator.py # LangGraph supervisor
│   │   │   ├── job_search.py
│   │   │   ├── resume_agent.py
│   │   │   ├── linkedin_agent.py
│   │   │   ├── email_agent.py
│   │   │   ├── followup_agent.py
│   │   │   └── rag_agent.py
│   │   ├── core/
│   │   │   ├── config.py       # pydantic-settings, all env vars
│   │   │   ├── model_router.py # BYOK resolver → BaseChatModel
│   │   │   ├── security.py     # AES-256 encrypt/decrypt, PBKDF2
│   │   │   └── database.py     # Supabase async client, session factory
│   │   ├── models/
│   │   │   ├── db.py           # SQLAlchemy table definitions
│   │   │   └── schemas.py      # Pydantic request/response schemas
│   │   └── services/
│   │       ├── rag_service.py  # chunk, embed, store, retrieve
│   │       ├── pdf_service.py  # ReportLab resume PDF generation
│   │       └── queue_service.py # BullMQ job enqueue via Redis
│   ├── tests/
│   │   ├── unit/               # all LLM calls mocked, runs in CI
│   │   │   ├── test_model_router.py
│   │   │   ├── test_security.py
│   │   │   ├── test_rag_service.py
│   │   │   ├── test_resume_agent.py
│   │   │   ├── test_job_search_agent.py
│   │   │   └── test_pdf_service.py
│   │   ├── integration/        # real APIs, run with INTEGRATION=1 pytest tests/integration/
│   │   │   ├── test_resume_flow.py
│   │   │   ├── test_rag_pipeline.py
│   │   │   └── test_job_search_flow.py
│   │   └── conftest.py         # fixtures: mock_llm, test_db, test_user
│   ├── requirements.txt
│   └── pyproject.toml          # ruff, black, pytest config
├── worker/
│   ├── src/
│   │   ├── index.ts            # BullMQ worker entrypoint
│   │   ├── queues/
│   │   │   └── agent-queue.ts
│   │   └── processors/
│   │       ├── job-search.processor.ts
│   │       └── followup.processor.ts
│   ├── package.json
│   └── tsconfig.json
├── supabase/
│   ├── migrations/
│   │   ├── 0001_create_users.sql
│   │   ├── 0002_create_model_settings.sql
│   │   ├── 0003_create_documents.sql
│   │   ├── 0004_create_applications.sql
│   │   ├── 0005_create_leads.sql
│   │   ├── 0006_create_agent_runs.sql
│   │   └── 0007_create_pgvector_indexes.sql
│   └── seed.sql
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── Makefile                    # convenience targets: make dev, make test, make lint
├── CLAUDE.md
└── README.md
```

---

## 4. Agent Architecture

### 4.1 Shared State

```python
# backend/app/agents/state.py
from typing import TypedDict, Literal
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    user_id: str
    run_id: str
    task_type: str
    messages: list[BaseMessage]
    context: dict                          # RAG chunks, JD text, company intel
    status: Literal["running", "awaiting_approval", "completed", "failed"]
    pending_action: dict | None            # email draft or apply payload, awaits human gate
    result: dict | None
    error: str | None
```

### 4.2 Orchestrator Pattern

LangGraph `StateGraph` with supervisor routing. The orchestrator decides which sub-agent handles the current task step, then routes back to itself or terminates.

```
START → orchestrator
orchestrator → job_search | resume | linkedin | email | followup | rag | END
each sub-agent → orchestrator (for next step) or END
```

### 4.3 Human-in-Loop Gate

1. Agent reaches a destructive action (send email, submit application)
2. Sets `state["status"] = "awaiting_approval"`, populates `state["pending_action"]`
3. LangGraph pauses via interrupt mechanism
4. SSE pushes `{"type": "checkpoint", "data": pending_action}` to frontend
5. `ApprovalModal` renders action details
6. User approves → `POST /api/v1/agents/{run_id}/approve` → graph resumes
7. User rejects → `POST /api/v1/agents/{run_id}/cancel` → graph terminates cleanly

**This gate is non-bypassable.** No code path sends emails or submits applications without hitting this checkpoint.

---

## 5. Model Router

```python
# backend/app/core/model_router.py
from app.core.security import decrypt_aes256
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

def get_llm(user_id: str, db) -> BaseChatModel:
    settings = (
        db.query(UserModelSettings)
        .filter_by(user_id=user_id, is_active=True)
        .first()
    )
    if not settings:
        raise HTTPException(status_code=400, detail="No active model configured")
    
    api_key = decrypt_aes256(settings.api_key_enc)  # decrypted at runtime only
    
    match settings.provider:
        case "anthropic":
            return ChatAnthropic(model=settings.model_name, api_key=api_key)
        case "openai":
            return ChatOpenAI(model=settings.model_name, api_key=api_key)
        case "google":
            return ChatGoogleGenerativeAI(model=settings.model_name, api_key=api_key)
        case "ollama":
            return ChatOllama(model=settings.model_name, base_url=settings.ollama_url)
        case "nvidia_nim":
            return ChatOpenAI(
                model=settings.model_name,
                api_key=api_key,
                base_url="https://integrate.api.nvidia.com/v1"
            )
        case _:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {settings.provider}")
```

- `APP_SECRET_KEY` env var drives PBKDF2 key derivation, never stored in DB
- API key decrypted only within request lifecycle, not cached in memory

---

## 6. Real-Time Streaming (SSE)

```
LangGraph agent (asyncio background task)
    │
    └── LangChain callbacks → asyncio.Queue (keyed by run_id)
                                    │
GET /api/v1/agents/{run_id}/stream  │
    └── FastAPI StreamingResponse ──┘
        yields text/event-stream events
                │
        Frontend EventSource(url)
                │
        useAgentStream(runId) hook
                │
        Zustand agentSlice update
                │
        AgentStatusStream component renders
```

**Event schema:**
```json
{ "type": "log", "data": "Searching LinkedIn for Python engineer roles...", "ts": 1748001234 }
{ "type": "checkpoint", "data": { "action": "apply", "company": "Stripe", "role": "SWE" }, "ts": 1748001290 }
{ "type": "error", "data": "PinchTab: rate limit detected, retrying in 30s", "ts": 1748001310 }
{ "type": "complete", "data": { "jobs_found": 12, "applied": 0 }, "ts": 1748001400 }
```

SSE connection auto-closes on `complete` or `error` event. Frontend EventSource reconnects on unexpected disconnect (max 3 attempts, exponential backoff).

---

## 7. RAG Pipeline

### 7.1 Ingestion

```
Upload (PDF/DOCX)
    → Supabase Storage (raw file)
    → Text extract: PyMuPDF (PDF) / python-docx (DOCX)
    → RecursiveCharacterTextSplitter(chunk_size=500, overlap=50)
    → Embedding: provider from user model settings
        OpenAI  → text-embedding-3-small
        Google  → models/embedding-001
        Ollama  → nomic-embed-text
        Anthropic → fallback to nomic-embed-text (no native embeddings)
    → LangChain PGVector: collection = {user_id}_{doc_type}
    → user_documents row updated: embedded_at = NOW()
```

### 7.2 Retrieval

```python
def retrieve(user_id: str, doc_type: str, query: str, k: int = 5) -> list[Document]:
    store = PGVector(collection_name=f"{user_id}_{doc_type}", ...)
    return store.similarity_search(query, k=k)
```

HNSW index created in migration 0007 for production query performance.

---

## 8. Testing Strategy

### 8.1 Backend

| Suite | Command | When |
|---|---|---|
| Unit (mocked LLM) | `pytest tests/unit` | Every PR, runs in CI |
| Integration (real APIs) | `INTEGRATION=1 pytest tests/integration/` | Pre-merge to main, manual trigger |

**Mock pattern:**
```python
# tests/conftest.py
@pytest.fixture
def mock_llm():
    with patch("app.core.model_router.get_llm") as m:
        m.return_value = FakeChatModel(responses=["mocked response"])
        yield m
```

### 8.2 Frontend

```
jest + React Testing Library
- Component tests: render + user interaction
- Hook tests: useAgentStream, TanStack Query factories
- No snapshot tests (brittle)
```

### 8.3 Security Tests

- Bandit (Python SAST) in CI — blocks PR on HIGH severity
- `npm audit --audit-level=high` in CI
- Manual security review checklist in PR template

---

## 9. Git Workflow

### 9.1 Branches

```
main     → production, protected: requires PR + CI green + 1 review
develop  → staging integration, auto-deploys to staging env
feature/xxx  → branches off develop, merges back to develop
fix/xxx      → bug fixes, branches off develop
hotfix/xxx   → critical prod fix, branches off main, merges to main + develop
```

### 9.2 Commit Convention (Conventional Commits)

```
feat(agent):    new agent capability or endpoint
fix(rag):       bug fix in RAG pipeline
test(resume):   add/modify tests
docs(adr):      architecture decision record
chore(docker):  infra/tooling change with no production behavior change
refactor(core): internal restructure, no behavior change
security:       security fix (use this type for any security patch)
```

### 9.3 PR Process

1. Branch off `develop`
2. PR against `develop` — CI must pass (lint + unit tests + Bandit)
3. PR description: what, why, test coverage, security checklist
4. Screenshots required for any UI change
5. Integration tests run on merge to `develop`
6. `develop → main` PR requires passing integration suite

---

## 10. Security

| Concern | Control |
|---|---|
| API key storage | AES-256 encrypted, PBKDF2 key derivation from `APP_SECRET_KEY`, never logged |
| Authentication | Clerk JWT verified via FastAPI dependency on every protected route |
| Rate limiting | `slowapi`: 60 req/min per user on all endpoints |
| Python SAST | Bandit in CI, blocks on HIGH severity |
| Frontend deps | `npm audit --audit-level=high` in CI |
| Browser isolation | PinchTab: separate browser context per `user_id` |
| Human gate | Required before every email send or job application submit |
| Audit trail | All agent actions logged to `agent_runs` (input, output, tokens, duration) |
| Transport | HTTPS enforced via Nginx + Certbot (Let's Encrypt) |
| Secrets | `.env` gitignored, `.env.example` documents all vars without values |
| SQL injection | SQLAlchemy ORM only — no raw query string construction |

---

## 11. Documentation Standards

| Type | Location | When |
|---|---|---|
| Design specs | `docs/superpowers/specs/YYYY-MM-DD-topic.md` | Before implementation starts |
| ADRs | `docs/adr/ADR-NNN-title.md` | Any non-obvious architectural decision |
| API docs | Auto-generated from FastAPI OpenAPI at `/docs` | Kept current via docstrings on route handlers |
| Runbooks | `docs/runbooks/` | Deploy, rollback, env setup, incident response |
| CLAUDE.md | Root | Updated when architecture changes |

**Code comments:** Only for non-obvious WHY. No what-comments, no docblocks describing obvious behavior.

---

## 12. Build Phases

Matches PRD §7 with added detail:

| Phase | Deliverables | Key Files |
|---|---|---|
| P1: Foundation | Repo scaffold, Docker Compose, Supabase schema, Clerk auth, model router | `supabase/migrations/`, `backend/app/core/`, `frontend/(auth)/` |
| P2: RAG | Document upload, chunk/embed/store, retrieval service, pgvector HNSW index | `backend/app/services/rag_service.py`, `backend/app/api/v1/rag.py` |
| P3: Resume + LinkedIn | Resume Agent (RAG + ReportLab PDF), LinkedIn Agent (PinchTab) | `backend/app/agents/resume_agent.py`, `backend/app/services/pdf_service.py` |
| P4: Job Search | Job Search Agent, PinchTab browser automation, BullMQ queue | `backend/app/agents/job_search.py`, `worker/` |
| P5: Email + Follow-Up | Gmail MCP integration, Email Agent, Follow-Up Agent + scheduler | `backend/app/agents/email_agent.py`, `backend/app/agents/followup_agent.py` |
| P6: Orchestrator | LangGraph supervisor, full agent loop, kanban dashboard frontend | `backend/app/agents/orchestrator.py`, `frontend/src/app/applications/` |
| P7: Production | Nginx SSL, Docker hardening, load test, security audit, rate limit tuning | `nginx/`, CI/CD pipeline |

---

*JobAgent AI Design — 2026-05-23 — Confidential*
