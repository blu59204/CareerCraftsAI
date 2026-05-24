# JobAgent AI

> **Automate your entire job search with a harness of AI agents — from finding roles to submitting applications, optimizing your LinkedIn profile, and following up with recruiters.**

Bring your own AI API key. Pay only for what you use. Your data stays yours.

---

## What It Does

JobAgent AI deploys specialized agents that work together to handle every step of your job search:

| Agent | What it does |
|---|---|
| **Job Search** | Browses LinkedIn, scores matches against your profile (0–100), returns ranked results |
| **Resume** | Retrieves your experience via RAG, rewrites resume for a specific JD, generates PDF |
| **LinkedIn** | Rewrites headline, About section, and experience bullets for a target role |
| **Email** | Reads your Gmail threads for context, drafts personalized outreach |
| **Follow-Up** | Automatically schedules day-5 and day-12 follow-up emails after you apply |
| **Orchestrator** | LangGraph supervisor that routes tasks and streams live progress to your browser |

Every action that sends an email or submits an application requires **explicit human approval** — agents prepare, you decide.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Next.js 14 App Router  (port 3000)                 │
│  Dashboard · Resume · Jobs · Applications · Email   │
└────────────────────────┬────────────────────────────┘
                         │ REST + SSE
┌────────────────────────▼────────────────────────────┐
│  FastAPI  (port 8000)                               │
│  /agents · /resume · /jobs · /rag · /email          │
└────────┬───────────────────────────┬────────────────┘
         │ LangGraph                 │ Redis / BullMQ
┌────────▼──────────┐    ┌──────────▼─────────────────┐
│  Agent Harness    │    │  BullMQ Worker  (Node.js)  │
│  Orchestrator     │    │  Job Search · Follow-Up    │
│  Resume · LinkedIn│    └────────────────────────────┘
│  Email · FollowUp │
└────────┬──────────┘
         │
┌────────▼──────────────────────────────────────────┐
│  Supabase Cloud                                    │
│  PostgreSQL 16 · pgvector · Storage · Auth        │
└───────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────┐
│  Model Router  (BYOK)                              │
│  Claude · GPT · Gemini · Ollama · NVIDIA NIM      │
└───────────────────────────────────────────────────┘
```

**Infrastructure:** Hybrid — Supabase Cloud + Clerk Cloud for managed services, Docker Compose on your VPS for application logic.

---

## Tech Stack

**Backend**
- Python 3.12 · FastAPI 0.136 · SQLAlchemy 2.0 async
- LangGraph 1.2 · LangChain 1.3 · langchain-postgres 0.0.17
- AES-256-GCM API key encryption (PBKDF2 key derivation)
- Redis 7 + BullMQ 5 · PinchTab 0.7.6 (browser automation)

**Frontend**
- Next.js 14 App Router · TypeScript · Tailwind CSS
- shadcn/ui · Zustand 4 · TanStack Query 5 · Clerk

**Infrastructure**
- Supabase (PostgreSQL + pgvector + Storage)
- Docker Compose · Nginx (TLS 1.2/1.3 + security headers)
- GitHub Actions CI/CD

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- [Supabase](https://supabase.com) project (free tier works)
- [Clerk](https://clerk.com) app (free tier works)
- At least one AI provider API key (Anthropic, OpenAI, Google, or local Ollama)

### 1. Clone and configure

```bash
git clone <repo-url>
cd jobagent-ai
cp .env.example .env
```

Open `.env` and fill in:

```bash
# Required
APP_SECRET_KEY=<generate with: openssl rand -hex 32>
DATABASE_URL=postgresql+asyncpg://postgres:[password]@db.[project].supabase.co:5432/postgres
SUPABASE_URL=https://[project].supabase.co
SUPABASE_SERVICE_KEY=<from Supabase dashboard>
CLERK_SECRET_KEY=<from Clerk dashboard>
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<from Clerk dashboard>
REDIS_URL=redis://redis:6379
```

### 2. Run database migrations

```bash
supabase db push --db-url "$DATABASE_URL"
```

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

Go to **Settings → AI Models** in the app and add your API key for at least one provider.

### 5. Upload your resume

Go to **Resume → Upload** and upload your current resume (PDF or DOCX). This seeds the RAG pipeline that all agents use as context.

---

## Development

### Commands

```bash
make dev              # start full stack (hot reload)
make test             # run unit tests (40 tests)
make lint             # ruff + eslint check
make format           # ruff --fix + black + eslint --fix
make build            # build all Docker images
make clean            # stop containers, remove volumes
```

### Backend only

```bash
cd backend
source .venv/bin/activate

# Run tests
pytest tests/unit -v                  # 40 unit tests
pytest tests/security -v             # 6 security tests
pytest tests/unit tests/security -v  # all 46 tests
pytest -k "test_security" -v         # single test by name

# Install dependencies (use constraints to block CVE-affected packages)
pip install -r requirements.txt -c constraints.txt

# Security scan
bandit -r app/ -f txt

# Lint
ruff check . && black --check .
```

### Frontend only

```bash
cd frontend
npm install
npm run dev           # dev server :3000
npm run build         # production build
npm run lint          # eslint
npm run type-check    # tsc --noEmit
```

### Worker only

```bash
cd worker
npm install
npm run build         # compile TypeScript
npm run dev           # ts-node (dev)
```

---

## Project Structure

```
jobagent-ai/
├── backend/
│   ├── app/
│   │   ├── agents/          # LangGraph nodes (resume, linkedin, job_search, email, followup, orchestrator)
│   │   ├── api/v1/          # FastAPI route handlers
│   │   ├── core/            # config, security (AES-256), database, model_router, event_bus
│   │   ├── models/          # SQLAlchemy ORM + Pydantic schemas
│   │   └── services/        # rag, pdf, storage, gmail, pinchtab, queue, resend
│   └── tests/
│       ├── unit/            # 40 tests — all mocked, fast CI
│       ├── security/        # 6 tests — auth enforcement, input validation
│       └── integration/     # opt-in (INTEGRATION=1) — real Supabase + real LLM
├── frontend/
│   └── src/
│       ├── app/             # Next.js App Router pages
│       ├── components/      # UI components + agent stream + approval modal
│       ├── lib/             # axios client, SSE hook
│       └── store/           # Zustand slices (agents, user)
├── worker/
│   └── src/
│       └── processors/      # BullMQ job processors (job-search, followup)
├── supabase/
│   └── migrations/          # 7 SQL migrations (users → pgvector indexes)
├── nginx/nginx.conf          # TLS + security headers + /internal blocked
├── docker-compose.yml        # production stack
├── docker-compose.dev.yml    # dev stack (hot reload)
├── locustfile.py             # load test baseline
└── constraints.txt           # pip security constraints (blocks CVE packages)
```

---

## Supported AI Providers

| Provider | Chat Models | Embeddings |
|---|---|---|
| **Anthropic** | Claude Sonnet 4.6, Haiku 4.5 | — (falls back to nomic-embed-text) |
| **OpenAI** | GPT-4o, GPT-4o-mini | text-embedding-3-small |
| **Google** | Gemini 2.0 Flash, Pro | models/embedding-001 |
| **Ollama** | Any local model | nomic-embed-text |
| **NVIDIA NIM** | Llama 3.1 70B, others | — (falls back to nomic-embed-text) |

Multiple providers can be configured simultaneously — select the active model in Settings.

---

## API Overview

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/agents/run` | Start an agent run |
| `GET` | `/api/v1/agents/{id}/stream` | SSE live event stream |
| `POST` | `/api/v1/agents/{id}/approve` | Approve or cancel pending action |
| `POST` | `/api/v1/resume/optimize` | Generate tailored resume |
| `GET` | `/api/v1/resume/download/{id}` | Download PDF |
| `POST` | `/api/v1/rag/upload` | Upload document (PDF/DOCX/TXT) |
| `GET` | `/api/v1/jobs/applications` | List applications pipeline |
| `POST` | `/api/v1/email/compose` | Draft outreach email |
| `POST` | `/api/v1/email/approve/{id}` | Send approved email via Gmail |
| `GET` | `/health` | Health check |

Full interactive docs at `http://localhost:8000/docs` (dev mode).

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

This is enforced server-side — the `/approve` endpoint is the only code path that calls `send_message()`.

---

## Security

- **API keys** encrypted at rest with AES-256-GCM (PBKDF2, unique salt per key, decrypted only at request time)
- **Authentication** via Clerk JWT verified on every protected route
- **Rate limiting** 60 req/min per user via slowapi
- **Internal endpoints** (`/internal/*`) blocked at Nginx — worker calls never reach the public internet
- **Browser isolation** PinchTab creates a separate browser context per user
- **Dependency audit** `pip-audit` + `npm audit` in CI; `bandit` SAST on every PR
- **CVE-2025-68664** (LangChain serialization) — patched, using langchain-core 1.4.0
- **CVE-2025-67644** (LangGraph SQLite injection) — blocked via `constraints.txt`
- **langchain-community** sunset — replaced with `langchain-postgres` for vector store

---

## Deployment (Production)

### 1. VPS setup

```bash
# On your Ubuntu 22.04 VPS
mkdir -p /opt/jobagent
cd /opt/jobagent
git clone <repo-url> .
cp .env.example .env
# Fill in production values

# Get SSL certificate
certbot --nginx -d yourdomain.com

# Update nginx.conf — replace ${DOMAIN} with your domain
sed -i 's/${DOMAIN}/yourdomain.com/g' nginx/nginx.conf
```

### 2. Start production stack

```bash
docker compose up -d
docker compose ps   # verify all services healthy
curl https://yourdomain.com/health  # should return {"status":"ok"}
```

### 3. Run migrations

```bash
supabase db push --db-url "$DATABASE_URL"
```

### 4. Configure GitHub Actions secrets

Add these secrets in your repo → Settings → Secrets → Actions:

| Secret | Value |
|---|---|
| `VPS_HOST` | Your server IP or hostname |
| `VPS_USER` | SSH user (e.g. `ubuntu`) |
| `VPS_SSH_KEY` | Private SSH key content |

Pushes to `main` auto-deploy via `.github/workflows/cd.yml`.

---

## Post-Launch Checklist

- [ ] Run HNSW index migration after first RAG ingestion (see `supabase/migrations/0007_create_pgvector_indexes.sql`)
- [ ] Set Supabase RLS policies on all tables for extra DB-layer protection
- [ ] Configure Supabase DB connection pool alerts
- [ ] Enable Clerk production mode and set allowed origins
- [ ] Set `APP_ENV=production` in `.env` (disables `/docs` endpoint)
- [ ] Verify Redis `appendonly yes` is persisting to Docker volume
- [ ] Add BullBoard (`@bull-board/express`) to worker for queue visibility

---

## Documentation

| Document | Path |
|---|---|
| Product Requirements | `CareerCraft AI.md` |
| System Design | `docs/superpowers/specs/2026-05-23-jobagent-ai-design.md` |
| Implementation Plans | `docs/superpowers/plans/` |
| Architecture Decisions | `docs/adr/` |
| Claude Code context | `CLAUDE.md` |

---

## License

MIT
