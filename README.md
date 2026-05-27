# CareerCraft AI

> **A full-stack, multi-agent job search automation platform. Bring your own AI API key — agents handle everything from finding roles to submitting applications, optimizing your LinkedIn profile, researching companies, negotiating salary, and following up with recruiters.**

Your data stays yours. You pay only for your own AI usage.

---

## What It Does

CareerCraft AI deploys a harness of specialized AI agents that collaborate to automate every stage of your job search:

| Agent | What it does |
|---|---|
| **Orchestrator** | LangGraph supervisor — routes tasks, manages shared state, streams live progress |
| **Job Search** | Browses LinkedIn, Naukri, Indeed, and other job boards via PinchTab; scores matches 0–100 |
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

Every action that sends an email or submits an application requires **explicit human approval** — agents prepare, you decide.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js 14 App Router  (port 3000)                         │
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
│  Supabase Cloud                                            │
│  PostgreSQL 16 · pgvector · Storage · Auth                │
└───────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────┐
│  Model Router  (BYOK)                                      │
│  Claude · GPT · Gemini · Ollama · NVIDIA NIM              │
└───────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────┐
│  External Integrations                                     │
│  Hunter.io · ProxyCurl · Exa · YouTube · Resend           │
└───────────────────────────────────────────────────────────┘
```

**Infrastructure:** Hybrid — Supabase Cloud for managed services, Docker Compose on your VPS for application logic.

---

## Feature Highlights

### Auto-Apply Pipeline
End-to-end automated job application. The pipeline finds matching jobs, tailors your resume, fills out application forms using browser automation (PinchTab), and submits — all with a human approval gate before anything is sent.

Supports Indian job platforms (Naukri, Shine, Freshersworld) and international boards (LinkedIn, Indeed, Glassdoor).

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
- Redis 7 + BullMQ 5 · PinchTab 0.7.6 (browser automation)
- ReportLab 4 (PDF) · PyMuPDF + python-docx (parsing)
- Hunter.io · ProxyCurl · Exa · Resend integrations

**Frontend**
- Next.js 14 App Router · TypeScript 5 · Tailwind CSS
- shadcn/ui · Zustand 4 · TanStack Query 5
- Motion (Framer Motion successor) · Sonner notifications

**Infrastructure**
- Supabase (PostgreSQL 16 + pgvector 0.7+ + Storage + Auth)
- Docker Compose · Nginx (TLS 1.2/1.3 + security headers)
- GitHub Actions CI/CD

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- [Supabase](https://supabase.com) project (free tier works)
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
DATABASE_URL=postgresql+asyncpg://postgres:[password]@db.[project].supabase.co:5432/postgres
SUPABASE_URL=https://[project].supabase.co
SUPABASE_SERVICE_KEY=<from Supabase dashboard>
NEXT_PUBLIC_SUPABASE_URL=<from Supabase dashboard>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<from Supabase dashboard>
SUPABASE_JWT_SECRET=<from Supabase dashboard Settings → API>
REDIS_URL=redis://redis:6379

# Optional — enables additional features
HUNTER_API_KEY=<hunter.io key for email finding>
PROXYCURL_API_KEY=<proxycurl key for LinkedIn data>
EXA_API_KEY=<exa.ai key for web search>
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

Go to **Settings → AI Models** and add your API key for at least one provider.

### 5. Upload your resume

Go to **Resume → Upload** and upload your current resume (PDF or DOCX). This seeds the RAG pipeline that all agents use as context.

---

## Development

### Commands

```bash
make dev              # start full stack (hot reload)
make test             # run unit + security tests (46 tests)
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

pytest tests/unit -v               # 40 unit tests
pytest tests/security -v           # 6 security tests
pytest tests/unit tests/security -v  # all 46 tests
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
```

### Worker only

```bash
cd worker
npm install
npm run build
npm run dev           # ts-node (dev)
```

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
│   │   │   ├── supabase_auth.py          # JWT verification middleware
│   │   │   ├── event_bus.py              # Redis pub/sub for SSE
│   │   │   └── rate_limit.py             # slowapi (60 req/min/user)
│   │   └── services/
│   │       ├── rag_service.py            # pgvector ingestion + retrieval
│   │       ├── pdf_service.py            # ReportLab PDF generation
│   │       ├── ats_service.py            # ATS keyword scoring
│   │       ├── auto_apply_service.py     # Auto-apply orchestration
│   │       ├── form_filler_service.py    # Browser form filling
│   │       ├── browser_control_service.py # PinchTab browser control
│   │       ├── job_platforms_service.py  # Multi-platform job search
│   │       ├── indian_platforms_service.py # Naukri, Shine, etc.
│   │       ├── email_finder_service.py   # Hunter.io email lookup
│   │       ├── linkedin_automation_service.py # LinkedIn outreach
│   │       ├── linkedin_outreach_service.py   # Outreach queue
│   │       ├── hunter_service.py         # Hunter.io integration
│   │       ├── proxycurl_service.py      # ProxyCurl LinkedIn data
│   │       ├── exa_service.py            # Exa web search
│   │       ├── persona_service.py        # Resume persona management
│   │       ├── token_budget_service.py   # LLM token budget tracking
│   │       ├── llm_proxy_service.py      # LLM proxy + caching
│   │       ├── gmail_service.py          # Gmail MCP integration
│   │       ├── storage_service.py        # Supabase Storage
│   │       ├── queue_service.py          # BullMQ job enqueuing
│   │       ├── resend_service.py         # Transactional email
│   │       └── youtube_service.py        # YouTube interview prep
│   └── tests/
│       ├── unit/                         # 40 tests — mocked, fast CI
│       ├── security/                     # 6 tests — auth + input validation
│       └── integration/                  # opt-in (INTEGRATION=1)
├── frontend/src/
│   ├── app/
│   │   ├── (app)/                        # Authenticated routes
│   │   │   ├── dashboard/
│   │   │   ├── resume/
│   │   │   ├── jobs/
│   │   │   ├── applications/
│   │   │   ├── email/
│   │   │   ├── linkedin/
│   │   │   ├── interview/
│   │   │   ├── interview-prep/
│   │   │   ├── company/
│   │   │   ├── salary/
│   │   │   ├── leads/
│   │   │   ├── agents/
│   │   │   ├── onboarding/
│   │   │   └── settings/
│   │   ├── (auth)/                       # Login · Register
│   │   └── (marketing)/                  # Landing · Pricing · Docs · About
│   ├── components/                       # UI components + agent stream + approval modal
│   ├── lib/                              # axios client · SSE hook · supabase client
│   └── store/                            # Zustand slices (agents, user)
├── worker/src/
│   └── processors/
│       ├── job-search.processor.ts       # Scheduled job search
│       ├── followup.processor.ts         # Follow-up email scheduling
│       ├── daily-search.processor.ts     # Daily job discovery
│       └── status-check.processor.ts    # Application status polling
├── supabase/migrations/                  # 19 SQL migrations
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
| **Anthropic** | Claude Sonnet 4.6, Haiku 4.5 (+ extended thinking) | — (falls back to nomic-embed-text) |
| **OpenAI** | GPT-4o, GPT-4o-mini | text-embedding-3-small |
| **Google** | Gemini 2.0 Flash, Pro | models/embedding-001 |
| **Ollama** | Any local model | nomic-embed-text |
| **NVIDIA NIM** | Llama 3.1 70B, others | — (falls back to nomic-embed-text) |

Multiple providers can be configured simultaneously — select the active model in **Settings → AI Models**.

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
| `POST` | `/api/v1/cover-letter/generate` | Generate cover letter |
| `POST` | `/api/v1/interview/session` | Start mock interview session |
| `GET` | `/api/v1/company/{name}/research` | Get company intelligence |
| `POST` | `/api/v1/salary/benchmark` | Benchmark compensation |
| `POST` | `/api/v1/linkedin/optimize` | Optimize LinkedIn profile |
| `GET` | `/api/v1/leads` | List recruiter leads |
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

This is enforced server-side — the `/approve` endpoint is the only code path that triggers irreversible actions.

---

## Security

- **API keys** encrypted at rest with AES-256-GCM (PBKDF2, unique salt per key, decrypted only at request time)
- **Authentication** via Supabase JWT verified on every protected route (HS256, audience=`authenticated`)
- **Rate limiting** 60 req/min per user via slowapi
- **Internal endpoints** (`/internal/*`) blocked at Nginx — worker calls never reach the public internet
- **Browser isolation** PinchTab creates a separate browser context per user
- **Dependency audit** `pip-audit` + `npm audit` in CI; `bandit` SAST on every PR
- **CVE-2025-68664** (LangChain serialization) — patched, using langchain-core 1.4.0
- **CVE-2025-67644** (LangGraph SQLite injection) — blocked via `constraints.txt`
- **langchain-community** sunset — replaced with `langchain-postgres` for vector store

---

## Database Schema

19 migrations covering:

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
| 0009 | Clerk → Supabase Auth migration |
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

### 3. Run migrations

```bash
supabase db push --db-url "$DATABASE_URL"
```

### 4. Configure GitHub Actions secrets

| Secret | Value |
|---|---|
| `VPS_HOST` | Your server IP or hostname |
| `VPS_USER` | SSH user (e.g. `ubuntu`) |
| `VPS_SSH_KEY` | Private SSH key content |

Pushes to `main` auto-deploy via `.github/workflows/cd.yml`.

---

## Post-Launch Checklist

- [ ] Run HNSW index migration after first RAG ingestion (`0007_create_pgvector_indexes.sql`)
- [ ] Set `APP_ENV=production` in `.env` (disables `/docs` endpoint)
- [ ] Configure Supabase Auth providers (Google, LinkedIn, GitHub) and set allowed redirect URLs
- [ ] Add Google OAuth scopes: `gmail.send`, `gmail.readonly`, `drive.readonly`
- [ ] Verify Redis `appendonly yes` is persisting to Docker volume
- [ ] Configure Supabase DB connection pool alerts
- [ ] Add BullBoard (`@bull-board/express`) to worker for queue visibility
- [ ] Set Hunter.io, ProxyCurl, and Exa API keys for full feature coverage

---

## Documentation

| Document | Path |
|---|---|
| Product Requirements | `CareerCraft AI.md` |
| System Design | `docs/superpowers/specs/` |
| Implementation Plans | `docs/superpowers/plans/` |
| Architecture Decisions | `docs/adr/` |
| AI Assistant Context | `CLAUDE.md` |
| Agent Configuration | `AGENTS.md` |

---

## License

MIT
