# CareerCraft AI

> **A full-stack, multi-agent job search automation platform. Bring your own AI API key — agents handle everything from finding roles to submitting applications, optimizing your LinkedIn profile, researching companies, negotiating salary, and following up with recruiters.**

Your data stays yours. You pay only for your own AI usage.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-542%20passing-brightgreen.svg)](#testing)

---

## Table of Contents

- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Feature Highlights](#feature-highlights)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Development](#development)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Supported AI Providers](#supported-ai-providers)
- [API Overview](#api-overview)
- [Human-in-the-Loop](#human-in-the-loop)
- [Security](#security)
- [Database Schema](#database-schema)
- [Deployment](#deployment-production)
- [Documentation](#documentation)
- [License](#license)

---

## What It Does

CareerCraft AI deploys a harness of specialized AI agents that collaborate to automate every stage of your job search:

| Agent | What it does |
|---|---|
| **Orchestrator** | LangGraph supervisor — routes tasks, manages shared state, streams live progress |
| **Job Search** | Browses LinkedIn, Naukri, Indeed, and other job boards via Playwright; scores matches 0–100 |
| **Resume** | RAG-powered resume rewriting tailored to a specific JD; generates ATS-optimized PDF |
| **Cover Letter** | Generates personalized, role-specific cover letters with multiple tone variants |
| **LinkedIn** | Rewrites headline, About section, and experience bullets for a target role |
| **Email** | Reads Gmail threads for context, drafts personalized outreach to recruiters |
| **Follow-Up** | Schedules day-5 and day-12 follow-up emails automatically after you apply |
| **Email Monitor** | Monitors your inbox for recruiter replies and surfaces action items |
| **Interview Coach** | Conducts mock interviews, scores answers, gives structured feedback |
| **Interview Prep** | Generates role-specific question banks and study guides |
| **Company Research** | Deep-dives company culture, financials, news, Glassdoor signals, and interview patterns |
| **Salary Agent** | Benchmarks compensation using market data; generates negotiation scripts |
| **NL Search** | Natural-language job search — describe what you want in plain English |
| **Auto-Apply Pipeline** | End-to-end automated application: finds job → tailors resume → fills form → submits |
| **RAG** | Retrieves context from your uploaded documents via pgvector |

> Every action that sends an email or submits an application requires **explicit human approval** — agents prepare, you decide.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js 16 App Router  (port 3000)                         │
│  Dashboard · Resume · Jobs · Applications · Email           │
│  LinkedIn · Interview · Company · Salary · Leads · Settings │
└────────────────────────┬────────────────────────────────────┘
                         │ REST + SSE
┌────────────────────────▼────────────────────────────────────┐
│  FastAPI  (port 8000)                                        │
│  /agents · /resume · /jobs · /rag · /email · /interview     │
│  /company · /salary · /cover-letter · /linkedin · /leads    │
└────────┬───────────────────────────┬────────────────────────┘
         │ LangGraph                 │ Redis / BullMQ
┌────────▼──────────────┐  ┌─────────▼──────────────────────┐
│  Agent Harness        │  │  BullMQ Worker  (Node.js)      │
│  Orchestrator         │  │  Job Search · Follow-Up        │
│  Resume · LinkedIn    │  │  Daily Search · Status Check   │
│  Email · FollowUp     │  └────────────────────────────────┘
│  Cover Letter         │
│  Interview Coach      │
│  Company Research     │
│  Salary · NL Search   │
│  Auto-Apply Pipeline  │
│  Email Monitor        │
└────────┬──────────────┘
         │
┌────────▼──────────────────────────────────────────────────┐
│  Self-hosted data layer                                    │
│  PostgreSQL 16 · pgvector · Redis 7 · local doc store     │
└───────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────┐
│  Model Router  (BYOK)                                      │
│  Claude · GPT · Gemini · DeepSeek · OpenRouter · Ollama   │
└───────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────┐
│  External Integrations                                     │
│  Nango (Gmail/Drive) · Hunter · ProxyCurl · Exa · Resend  │
└───────────────────────────────────────────────────────────┘
```

**Infrastructure:** Everything runs under Docker Compose on your own host — self-hosted PostgreSQL 16 + pgvector, Redis, and local-disk document storage. Authentication is [Clerk](https://clerk.com); Gmail/Drive access goes through the [Nango](https://nango.dev) credential proxy; durable auto-apply workflows can optionally run on [Temporal](https://temporal.io) (`TEMPORAL_ENABLED`).

> See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.

---

## Feature Highlights

### Auto-Apply Pipeline
End-to-end automated job application. The pipeline finds matching jobs, tailors your resume, fills out application forms using browser automation (Playwright), and submits — all with a human approval gate before anything is sent. Supports Indian job platforms (Naukri, Shine, Freshersworld) and international boards (LinkedIn, Indeed, Glassdoor).

### ATS Scoring
Every generated resume is scored against the target job description using keyword analysis, section completeness, and formatting rules. Score and improvement suggestions are shown before you download.

### Company Intelligence
Deep research on any company: culture signals, recent news, funding history, Glassdoor ratings, interview patterns, and key people — all synthesized into a structured briefing.

### Salary Benchmarking
Market compensation data for any role + location, with percentile breakdowns and a ready-to-use negotiation script tailored to your experience level.

### Interview Coach
Live mock interview sessions with AI feedback. Scores your answers on clarity, relevance, and depth. Tracks improvement across sessions.

### Natural Language Job Search
Describe what you want in plain English ("senior backend role at a climate startup, remote, $150k+") and the agent translates it into structured search queries across multiple job boards.

### LinkedIn Outreach Automation
Finds recruiter contact info via Hunter.io and ProxyCurl, drafts personalized connection requests and InMails, and queues them for your approval.

### Resume Personas
Maintain multiple resume personas (e.g., "Backend Engineer", "Tech Lead", "Startup Generalist") — each with its own RAG context and tailoring strategy.

### Email Monitoring
Watches your inbox for recruiter replies, surfaces threads that need action, and drafts responses — so nothing falls through the cracks.

### Extended Thinking
Agents can use Claude's extended thinking mode for complex tasks like cover letter generation and salary negotiation, producing higher-quality, more nuanced outputs.

### Token Budget Management
Tracks LLM token usage per user per agent run. Enforces configurable budgets to prevent runaway costs on BYOK keys.

---

## Tech Stack

**Backend**
- Python 3.12 · FastAPI 0.111+ · SQLAlchemy 2.0 async
- LangGraph 0.2+ · LangChain 0.3+ · langchain-postgres 0.0.17
- AES-256-GCM API key encryption (PBKDF2 key derivation)
- Redis 7 + BullMQ 5 · Playwright/Chromium (browser automation)
- Temporal (optional, durable auto-apply workflows) · Nango (OAuth credential proxy)
- ReportLab 4 (PDF) · PyMuPDF + python-docx (parsing)
- Hunter.io · ProxyCurl · Exa · Resend integrations

**Frontend**
- Next.js 16.2.6 App Router · TypeScript 6 · Tailwind CSS 3.4
- shadcn/ui · Zustand 4 · TanStack Query 5
- Motion (Framer Motion successor) · Sonner notifications · Three.js

**Infrastructure**
- Self-hosted PostgreSQL 16 + pgvector 0.7+ · local-disk document storage
- Clerk authentication (Google, LinkedIn, GitHub, email/password, magic link)
- Docker Compose · Nginx (TLS 1.2/1.3 + security headers)
- GitHub Actions CI/CD

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- A [Clerk](https://clerk.com) application (free tier works)
- PostgreSQL 16 with the `pgvector` extension (the Compose stacks provide one)
- At least one AI provider API key (Anthropic, OpenAI, Google, or local Ollama)

### 1. Clone and configure

```bash
git clone https://github.com/blu59204/CareerCraftsAI.git
cd CareerCraftsAI
cp .env.example .env
```

Open `.env` and fill in:

```bash
# Required
APP_SECRET_KEY=<generate with: openssl rand -hex 32>
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname
CLERK_ISSUER=https://[your-instance].clerk.accounts.dev
CLERK_SECRET_KEY=<from Clerk dashboard → API keys>
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<from Clerk dashboard → API keys>
REDIS_URL=redis://redis:6379
INTERNAL_SECRET=<shared secret between backend and worker>

# Required if your active model has no embeddings API (Anthropic, DeepSeek,
# OpenRouter, NVIDIA NIM): which provider embeds documents for RAG
EMBEDDING_PROVIDER=ollama   # openai | google | ollama

# Optional — enables additional features
HUNTER_API_KEY=<hunter.io key for email finding>
PROXYCURL_API_KEY=<proxycurl key for LinkedIn data>
EXA_API_KEY=<exa.ai key for web search>
RESEND_API_KEY=<resend.com key for transactional email>
NANGO_SECRET_KEY=<Nango secret — enables Gmail/Drive integrations>
TEMPORAL_ENABLED=false   # true to run auto-apply on Temporal
```

`.env.example` documents every variable.

### 2. Run database migrations

The SQL files in `supabase/migrations/` are plain PostgreSQL (the directory name is historical). Apply `deploy/oracle/postgres-bootstrap.sql` once first — it creates the roles and `auth.*` helper functions the migrations reference — then every migration in filename order:

```bash
PGURL=postgresql://user:password@host:5432/dbname   # libpq form, not +asyncpg
psql "$PGURL" -f deploy/oracle/postgres-bootstrap.sql
for f in supabase/migrations/*.sql; do psql "$PGURL" -v ON_ERROR_STOP=1 -f "$f"; done
```

One error is expected: the last statement of `0009_clerk_to_supabase.sql` creates a signup trigger on Supabase's `auth.users` table, which doesn't exist on plain PostgreSQL. It is safe to ignore, because the API provisions users on their first authenticated request.

### 3. Start the stack

```bash
make dev
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API docs | http://localhost:8000/docs |
| Redis | localhost:6379 |

### 4. Add your AI model

Go to **Settings → Models** and add your API key for at least one provider.

### 5. Upload your resume

Go to **Resume → Upload** and upload your current resume (PDF or DOCX). This seeds the RAG pipeline that all agents use as context.

---

## Development

### Commands

```bash
make dev              # start full stack (hot reload)
make test             # run backend unit tests
make test-integration # run integration tests (needs Postgres/Redis)
make lint             # ruff + eslint check
make format           # ruff --fix + black + eslint --fix
make build            # build all Docker images
make clean            # stop containers, remove volumes
```

### Backend only

```bash
cd backend
source .venv/bin/activate          # Linux/macOS
# .venv_win\Scripts\activate       # Windows

pip install -r requirements.txt -c constraints.txt

uvicorn app.main:app --reload --port 8000

pytest tests/unit tests/security -v  # ~540 tests, mocked, no network
pytest -k "test_name" -v           # single test

bandit -r app/ -f txt              # SAST scan
ruff check . && black --check .    # lint
```

### Frontend only

```bash
cd frontend
npm install
npm run dev           # dev server :3000
npm run build
npm run lint
npm run type-check    # tsc --noEmit
npm run test          # jest
```

### Worker only

```bash
cd worker
npm install
npm run build
npm run dev           # ts-node (dev)
```

> See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the full development guide.

---

## Testing

| Suite | Command | Needs |
|---|---|---|
| Unit + security | `cd backend && pytest tests/unit tests/security` | nothing — fully mocked |
| Integration | `cd backend && pytest tests/integration` | Postgres + Redis (`docker compose -f docker-compose.test.yml up -d`); LLM-backed cases also need `INTEGRATION=1` and a real provider key |
| End-to-end collection | `pytest backend/tests/e2e --collect-only` | nothing — runs in CI on every PR |
| Live end-to-end | `bash scripts/run_e2e_tests.sh` | a running stack plus `TEST_JWT`, `TEST_EMAIL`, `TEST_PASSWORD`, `WEB_URL`, `API_URL` |
| Frontend | `cd frontend && npm run type-check && npm run lint && npm run build` | Node 24 |

The live suite signs in through the real Clerk UI, loads all 20 authenticated screens at desktop and mobile widths, walks each screen's main user journey, and drives all 15 agent responsibilities through the API (`backend/tests/e2e/`). It **never approves** an email send, LinkedIn message, or job application: approval checkpoints are asserted and then rejected. Real sends require `ALLOW_LIVE_SENDS=1`; Gmail draft creation requires `ALLOW_GMAIL_DRAFTS=1`. Screenshots, videos and traces go to gitignored `backend/tests/e2e/.artifacts/`.

In CI, `.github/workflows/ci.yml` runs unit, security, integration, frontend and e2e-collection jobs on every PR; the live suite runs only on a manual `workflow_dispatch` and uploads its artifacts even on failure.

---

## Project Structure

```
CareerCraftsAI/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── orchestrator.py           # LangGraph supervisor
│   │   │   ├── harness.py                # Agent harness entry point
│   │   │   ├── job_search.py             # Job board search + scoring
│   │   │   ├── resume_agent.py           # RAG resume tailoring + PDF
│   │   │   ├── cover_letter_agent.py     # Cover letter generation
│   │   │   ├── linkedin_agent.py         # LinkedIn profile optimization
│   │   │   ├── email_agent.py            # Recruiter outreach drafting
│   │   │   ├── email_monitor_agent.py    # Inbox monitoring + reply drafting
│   │   │   ├── followup_agent.py         # Scheduled follow-up emails
│   │   │   ├── interview_coach_agent.py  # Mock interviews + scoring
│   │   │   ├── interview_prep_agent.py   # Question banks + study guides
│   │   │   ├── company_research_agent.py # Company intelligence briefings
│   │   │   ├── salary_agent.py           # Salary benchmarking + negotiation
│   │   │   ├── nl_search_agent.py        # Natural language job search
│   │   │   ├── auto_apply_pipeline.py    # End-to-end auto-apply
│   │   │   ├── thinking.py               # Extended thinking utilities
│   │   │   ├── state.py                  # Shared LangGraph state schema
│   │   │   ├── strategies.py             # Agent strategy helpers
│   │   │   └── memory/                   # Agent memory manager
│   │   ├── api/v1/
│   │   │   ├── agents.py                 # Agent run + stream + approve
│   │   │   ├── resume.py                 # Resume optimize + download
│   │   │   ├── jobs.py                   # Job search + applications
│   │   │   ├── email.py                  # Email compose + send
│   │   │   ├── rag.py                    # Document upload + retrieval
│   │   │   ├── interview.py              # Interview coach sessions
│   │   │   ├── interview_prep.py         # Question banks
│   │   │   ├── cover_letter.py           # Cover letter generation
│   │   │   ├── company.py                # Company research
│   │   │   ├── salary.py                 # Salary benchmarking
│   │   │   ├── linkedin.py               # LinkedIn automation
│   │   │   ├── leads.py                  # Lead management
│   │   │   ├── users.py                  # User profile + preferences
│   │   │   └── deps.py                   # Auth + DB dependencies
│   │   ├── core/
│   │   │   ├── config.py                 # pydantic-settings config
│   │   │   ├── database.py               # Async SQLAlchemy engine
│   │   │   ├── security.py               # AES-256-GCM encryption
│   │   │   ├── model_router.py           # BYOK model routing
│   │   │   ├── llm_gateway.py            # LLM gateway + token tracking
│   │   │   ├── supabase_auth.py          # Clerk JWT (RS256/JWKS) verification — historical file name
│   │   │   ├── event_bus.py              # Redis pub/sub for SSE
│   │   │   └── rate_limit.py             # slowapi (60 req/min/user)
│   │   └── services/
│   │       ├── rag_service.py            # pgvector ingestion + retrieval
│   │       ├── pdf_service.py            # ReportLab PDF generation
│   │       ├── ats_service.py            # ATS keyword scoring
│   │       ├── auto_apply_service.py     # Auto-apply orchestration
│   │       ├── browser_control_service.py # Playwright browser control
│   │       ├── job_platforms_service.py  # Multi-platform job search
│   │       ├── gmail_service.py          # Gmail MCP integration
│   │       ├── hunter_service.py         # Hunter.io integration
│   │       ├── proxycurl_service.py      # ProxyCurl LinkedIn data
│   │       ├── exa_service.py            # Exa web search
│   │       ├── token_budget_service.py   # LLM token budget tracking
│   │       ├── resend_service.py         # Transactional email
│   │       ├── integration_proxy_service.py # Nango credential proxy
│   │       ├── storage_service.py        # Local-disk document storage
│   │       └── workflow_service.py       # Durable agent runs + approvals
│   │   ├── workflows/                    # Temporal auto-apply workflow + activities
│   │   ├── workflow_worker.py            # Durable agent-run worker
│   │   └── temporal_worker.py            # Temporal worker (optional)
│   └── tests/
│       ├── unit/                         # mocked, fast CI
│       ├── security/                     # auth, HITL bypass, input validation
│       ├── integration/                  # Postgres/Redis-backed; LLM cases opt-in
│       └── e2e/                          # live Playwright + API suite
├── frontend/src/
│   ├── app/
│   │   ├── (app)/                        # Authenticated routes
│   │   ├── (auth)/                       # Login · Register
│   │   └── (marketing)/                  # Landing · Pricing · Docs · About
│   ├── components/                       # UI components + agent stream + approval modal
│   ├── lib/                              # axios client · agent-run polling · SSE · Clerk token · Nango connect
│   └── store/                            # Zustand slices (agents, user)
├── worker/src/
│   └── processors/
│       ├── job-search.processor.ts       # Scheduled job search
│       ├── followup.processor.ts         # Follow-up email scheduling
│       ├── daily-search.processor.ts     # Daily job discovery
│       └── status-check.processor.ts    # Application status polling
├── supabase/migrations/                  # 37 SQL migrations (plain PostgreSQL)
├── deploy/oracle/                        # Single-VM Compose stack, Nginx, Postgres bootstrap
├── scripts/run_e2e_tests.sh              # Live end-to-end runner with preflight checks
├── nginx/nginx.conf                      # TLS + security headers
├── docker-compose.yml                    # Production stack
├── docker-compose.dev.yml                # Dev stack (hot reload)
├── Makefile                              # Top-level dev commands
└── locustfile.py                         # Load test baseline
```

---

## Supported AI Providers

| Provider | Chat Models | Embeddings |
|---|---|---|
| **Anthropic** | Claude Sonnet 4.6, Haiku 4.5 (+ extended thinking) | — (uses `EMBEDDING_PROVIDER`) |
| **OpenAI** | GPT-4o, GPT-4o-mini | text-embedding-3-small |
| **Google** | Gemini 2.0 Flash, Pro | models/embedding-001 |
| **Ollama** | Any local model | nomic-embed-text |
| **NVIDIA NIM** | Llama 3.1 70B, others | — (uses `EMBEDDING_PROVIDER`) |
| **DeepSeek** | DeepSeek chat models | — (uses `EMBEDDING_PROVIDER`) |
| **OpenRouter** | Any model in the OpenRouter catalog | — (uses `EMBEDDING_PROVIDER`) |

Multiple providers can be configured simultaneously — select the active model in **Settings → Models**. Providers without an embeddings API use the provider named in `EMBEDDING_PROVIDER` (`openai`, `google`, or `ollama`) for RAG.

---

## API Overview

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/agents/run` | Start an agent run |
| `GET` | `/api/v1/agents/runs/{id}` | Poll a run's persisted status and output |
| `GET` | `/api/v1/agents/{id}/stream` | SSE live event stream |
| `POST` | `/api/v1/agents/{id}/approve` | Approve or cancel pending action |
| `POST` | `/api/v1/resume/optimize` | Generate tailored resume |
| `GET` | `/api/v1/resume/download/{id}` | Download PDF |
| `POST` | `/api/v1/rag/upload` | Upload document (PDF/DOCX/TXT) |
| `GET` | `/api/v1/jobs/applications` | List applications pipeline |
| `POST` | `/api/v1/email/compose` | Draft outreach email |
| `POST` | `/api/v1/email/approve/{id}` | Send approved email via Gmail |
| `POST` | `/api/v1/cover-letter/generate` | Generate cover letter |
| `POST` | `/api/v1/interview/session/start` | Start mock interview session |
| `POST` | `/api/v1/interview/session/{id}/answer` | Score an answer, get the next question |
| `GET` | `/api/v1/company/{name}/intel` | Get saved company intelligence |
| `POST` | `/api/v1/salary/report` | Benchmark compensation |
| `POST` | `/api/v1/linkedin/outreach/identify` | Find contacts and draft LinkedIn outreach |
| `GET` | `/api/v1/email/inbox-cleanup` | List promotional/update mail with unsubscribe links |
| `GET` | `/api/v1/integrations` | Gmail/Drive/Calendar connection status |
| `GET` | `/api/v1/leads` | List recruiter leads |
| `GET` | `/health` | Health check (app root, not under `/api/v1`) |

Long-running agents (company research, salary, interview prep, LinkedIn profile optimization) start with `POST /agents/run` and a `task_type`, then are polled via `GET /agents/runs/{id}`.

Full interactive docs at `http://localhost:8000/docs` (dev mode).

> See [docs/API.md](docs/API.md) for full API reference with request/response schemas.

---

## Human-in-the-Loop

No agent sends emails or submits applications without your explicit approval. The flow:

```
Agent completes task
        ↓
SSE pushes "checkpoint" event to browser
        ↓
ApprovalModal shows you exactly what will happen
        ↓
You click Approve → action executes
      OR
You click Cancel → action discarded
```

This is enforced server-side — the `/approve` endpoint is the only code path that triggers irreversible actions.

---

## Security

- **API keys** encrypted at rest with AES-256-GCM (PBKDF2, unique salt per key, decrypted only at request time)
- **Authentication** via Clerk session JWTs, verified locally on every protected route against Clerk's JWKS (RS256)
- **Data isolation** enforced in the API: every query is scoped to the authenticated user (RLS policies from the migrations remain as defense in depth)
- **Rate limiting** per-route limits via slowapi, keyed by user
- **Internal endpoints** (`/internal/*`) blocked at Nginx and gated by `INTERNAL_SECRET`; the worker refuses to start if its secret is rejected
- **Browser isolation** Playwright creates a separate browser context per user
- **Dependency audit** `pip-audit` + `npm audit` in CI; `bandit` SAST on every PR
- **CVE-2025-68664** (LangChain serialization) — patched, using langchain-core 1.4.0
- **CVE-2025-67644** (LangGraph SQLite injection) — blocked via `constraints.txt`
- **langchain-community** sunset — replaced with `langchain-postgres` for vector store

> See [docs/SECURITY.md](docs/SECURITY.md) for the full security posture.

---

## Database Schema

37 migrations in `supabase/migrations/`, including:

| Migration | Table / Change |
|---|---|
| 0001 | `users` |
| 0002 | `model_settings` |
| 0003 | `documents` |
| 0004 | `applications` |
| 0005 | `leads` |
| 0006 | `agent_runs` |
| 0007 | pgvector HNSW indexes |
| 0008 | Row-Level Security policies |
| 0009 | Auth provider migration (superseded by 0028) |
| 0010 | `user_preferences` |
| 0011 | `cover_letter_versions` |
| 0012 | `interview_sessions` |
| 0013 | `salary_reports` |
| 0014 | `company_intel` |
| 0015 | `resume_personas` |
| 0016 | `linkedin_outreach_queue` |
| 0017 | `ats_scores` |
| 0018 | RLS fix for `supabase_uid` |
| 0019 | LinkedIn credentials + auto mode |
| 0021 | Google OAuth tokens |
| 0025, 0032 | HNSW embedding indexes |
| 0028 | Clerk third-party auth RLS (`users.supabase_uid` holds the Clerk user id) |
| 0034 | Application attempts + outbound messages (send idempotency) |
| 0035 | Candidate profiles + saved form answers |
| 0036 | Temporal columns on application attempts |
| 0037 | Integration connections (Nango) |
| 20260909… | Durable agent workflow tables |

> See [docs/DATABASE.md](docs/DATABASE.md) for full schema reference with column types and RLS policies.

---

## Deployment (Production)

### 1. VPS setup

```bash
# On your Ubuntu 22.04 VPS
mkdir -p /opt/careercraft
cd /opt/careercraft
git clone https://github.com/blu59204/CareerCraftsAI.git .
cp .env.example .env
# Fill in production values

certbot --nginx -d yourdomain.com
sed -i 's/${DOMAIN}/yourdomain.com/g' nginx/nginx.conf
```

### 2. Start production stack

```bash
docker compose up -d
docker compose ps
curl https://yourdomain.com/health  # → {"status":"ok"}
```

For a single small VM, `deploy/oracle/compose.yml` runs the whole stack with host networking: backend, frontend, agent worker, BullMQ scheduler, self-hosted Postgres, Redis, Nginx gateway, the browser sandbox server, and an optional Temporal worker. Backend, frontend, Postgres and Redis have healthchecks, and services that depend on them wait until they are healthy.

### 3. Run migrations

Apply `deploy/oracle/postgres-bootstrap.sql` and then `supabase/migrations/*.sql` in order, as in [Quick Start step 2](#2-run-database-migrations). The Oracle Compose stack runs the bootstrap automatically on first start.

### 4. Configure GitHub Actions secrets

| Secret | Value |
|---|---|
| `VPS_HOST` | Your server IP or hostname |
| `VPS_USER` | SSH user (e.g. `ubuntu`) |
| `VPS_SSH_KEY` | Private SSH key content |

Pushes to `main` auto-deploy via `.github/workflows/cd.yml`.

> See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the complete production deployment guide.

---

## Post-Launch Checklist

- [ ] Confirm HNSW indexes exist after first RAG ingestion (migrations `0007`, `0025`, `0032`)
- [ ] Set `APP_ENV=production` in `.env` (disables `/docs` endpoint)
- [ ] Configure Clerk sign-in providers (Google, LinkedIn, GitHub) and allowed redirect origins
- [ ] Configure Nango Gmail/Drive integration keys and the verified webhook URL
- [ ] Verify Redis `appendonly yes` is persisting to Docker volume
- [ ] Set up PostgreSQL backups and connection-pool alerts
- [ ] When rotating `INTERNAL_SECRET`, recreate `scheduler` and `temporal-worker` too
- [ ] Add BullBoard (`@bull-board/express`) to worker for queue visibility
- [ ] Set Hunter.io, ProxyCurl, and Exa API keys for full feature coverage

---

## Documentation

| Document | Path | Description |
|---|---|---|
| Product Requirements | `CareerCraft AI.md` | Authoritative PRD |
| Architecture | `docs/ARCHITECTURE.md` | System design, data flows, decisions |
| API Reference | `docs/API.md` | Full endpoint docs with schemas |
| Database Schema | `docs/DATABASE.md` | All tables, columns, RLS policies |
| Deployment Guide | `docs/DEPLOYMENT.md` | VPS, Docker, CI/CD, SSL |
| Development Guide | `docs/DEVELOPMENT.md` | Local setup, testing, conventions |
| Security | `docs/SECURITY.md` | Auth, encryption, CVEs, auditing |
| E2E test plan | `docs/AGENT_FAILURE_ROOT_CAUSE_AND_E2E_TEST_PLAN.md` | Agent failure analysis and live test strategy |
| Nango integrations | `docs/NANGO_INTEGRATION.md` | Connect sessions, webhook setup, migration and rollback |
| Contributing | `docs/CONTRIBUTING.md` | PR process, code standards |
| Configuration | `docs/CONFIGURATION.md` | All environment variables |

---

## License

MIT
