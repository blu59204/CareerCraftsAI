# Project Structure

## Root Layout

```
jobagent-ai/
├── backend/          # Python FastAPI service (port 8000)
├── frontend/         # Next.js 14 App Router (port 3000)
├── worker/           # Node.js BullMQ worker
├── supabase/         # Database migrations
├── nginx/            # Reverse proxy config
├── scripts/          # Utility scripts
├── docs/             # Architecture decisions, design docs, plans
├── docker-compose.yml          # Production stack
├── docker-compose.dev.yml      # Dev stack (hot reload)
├── Makefile                    # Top-level dev commands
├── locustfile.py               # Load test definitions
├── CLAUDE.md                   # AI assistant context (authoritative)
└── CareerCraft AI.md           # Product Requirements Document
```

## Backend (`backend/`)

```
backend/
├── app/
│   ├── agents/           # LangGraph agent nodes
│   │   ├── orchestrator.py       # Supervisor agent
│   │   ├── job_search.py
│   │   ├── resume_agent.py
│   │   ├── linkedin_agent.py
│   │   ├── email_agent.py
│   │   ├── followup_agent.py
│   │   ├── interview_prep_agent.py
│   │   ├── harness.py            # Agent harness entry point
│   │   ├── state.py              # Shared LangGraph state schema
│   │   ├── strategies.py         # Agent strategy helpers
│   │   └── memory/               # Agent memory utilities
│   ├── api/
│   │   ├── v1/                   # Versioned route handlers
│   │   │   ├── deps.py           # FastAPI dependencies (auth, db)
│   │   │   ├── agents.py
│   │   │   ├── resume.py
│   │   │   ├── jobs.py
│   │   │   ├── email.py
│   │   │   ├── rag.py
│   │   │   ├── users.py
│   │   │   ├── leads.py
│   │   │   └── interview_prep.py
│   │   └── internal.py           # Internal endpoints (worker-only, blocked at Nginx)
│   ├── core/
│   │   ├── config.py             # Settings via pydantic-settings
│   │   ├── database.py           # Async SQLAlchemy engine + session factory
│   │   ├── security.py           # AES-256-GCM encryption/decryption
│   │   ├── model_router.py       # BYOK model routing (all LLM calls go here)
│   │   ├── supabase_auth.py      # JWT verification middleware
│   │   ├── event_bus.py          # Redis pub/sub for SSE
│   │   ├── rate_limit.py         # slowapi configuration
│   │   └── sync_db.py            # Sync DB utilities
│   ├── models/                   # SQLAlchemy ORM models + Pydantic schemas
│   ├── services/
│   │   ├── rag_service.py        # pgvector ingestion + retrieval
│   │   ├── pdf_service.py        # ReportLab PDF generation
│   │   ├── storage_service.py    # Supabase Storage upload/download
│   │   ├── gmail_service.py      # Gmail MCP integration
│   │   ├── pinchtab_service.py   # PinchTab browser automation
│   │   ├── queue_service.py      # BullMQ job enqueuing
│   │   ├── resend_service.py     # Transactional email via Resend
│   │   ├── ats_service.py        # ATS scoring
│   │   └── youtube_service.py
│   └── main.py                   # FastAPI app factory + router registration
├── tests/
│   ├── unit/                     # 40 tests — fully mocked, fast
│   ├── security/                 # 6 tests — auth enforcement, input validation
│   └── integration/              # Opt-in (INTEGRATION=1) — real Supabase + LLM
├── requirements.txt
├── constraints.txt               # Blocks CVE-affected packages — always use with pip install
└── pyproject.toml                # ruff, black, pytest config
```

## Frontend (`frontend/src/`)

```
frontend/src/
├── app/
│   ├── (app)/            # Authenticated app routes (dashboard, resume, jobs, etc.)
│   ├── (auth)/           # Auth flow pages
│   ├── (marketing)/      # Public marketing pages
│   ├── auth/             # Supabase auth callback handlers
│   ├── layout.tsx        # Root layout
│   └── globals.css
├── components/
│   ├── agents/           # Agent stream UI, approval modal
│   ├── apps/             # Feature-specific page components
│   ├── auth/             # Login/register forms
│   ├── layout/           # Shell, nav, sidebar
│   ├── marketing/        # Landing page components
│   ├── onboarding/       # New user onboarding flow
│   ├── resume/           # Resume builder/optimizer components
│   ├── theme/            # Theme provider
│   └── ui/               # shadcn/ui base components
├── lib/
│   ├── axios client      # Configured axios instance
│   └── SSE hook          # useEventSource / SSE utilities
├── store/
│   ├── agentSlice.ts     # Zustand: agent run state
│   └── userSlice.ts      # Zustand: user/session state
└── middleware.ts          # Supabase session refresh on every request
```

## Worker (`worker/src/`)

```
worker/src/
├── processors/           # BullMQ job processors (job-search, followup)
├── queues/               # Queue definitions and connection setup
└── index.ts              # Worker entry point
```

## Supabase (`supabase/`)

```
supabase/migrations/
├── 0001_create_users.sql
├── 0002_create_model_settings.sql
├── 0003_create_documents.sql
├── 0004_create_applications.sql
├── 0005_create_leads.sql
├── 0006_create_agent_runs.sql
├── 0007_create_pgvector_indexes.sql   # Run after first RAG ingestion
├── 0008_enable_rls.sql
├── 0009_clerk_to_supabase.sql
└── 0010_user_preferences.sql
```

## Key Conventions

- **API versioning:** All routes live under `/api/v1/`. New breaking changes get a new version prefix.
- **Auth dependency:** All protected backend routes use `deps.py` — import `get_current_user` from there, never roll your own JWT check.
- **Model calls:** Always go through `app/core/model_router.py`. Never instantiate a LangChain LLM directly with a hardcoded model name.
- **New agents:** Add the node file to `app/agents/`, register it in `harness.py`, and wire it into `orchestrator.py`.
- **New API routes:** Add a file to `app/api/v1/`, register the router in `app/main.py`.
- **New services:** Add to `app/services/`, inject via FastAPI `Depends()` where needed.
- **DB migrations:** Add a new numbered SQL file to `supabase/migrations/` — never edit existing migration files.
- **Frontend routes:** Follow the route groups — `(app)` for authenticated pages, `(auth)` for login/register, `(marketing)` for public pages.
- **Environment variables:** Backend config is centralized in `app/core/config.py` (pydantic-settings). Never read `os.environ` directly in application code.
