# Architecture

CareerCraft AI is a 4-layer system: Next.js frontend → FastAPI backend → LangGraph agent harness → Supabase + Redis data layer. All layers run in Docker Compose; Supabase is cloud-managed.

---

## System Diagram

```
Browser
   │  HTTPS
   ▼
┌──────────────────────────────────────────────┐
│  Nginx  (port 80/443)                        │
│  TLS termination · rate limiting · SSE proxy │
└──────────────┬───────────────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐  ┌─────────────────────────────┐
│  Next.js 14 │  │  FastAPI  (port 8000)        │
│  port 3000  │  │  REST + SSE                  │
│  App Router │  │  JWT auth on every route     │
│  Tailwind   │  │  60 req/min/user rate limit  │
│  Zustand    │  └──────────┬──────────────────┘
│  TanStack Q │             │
└─────────────┘    ┌────────┴──────────┐
                   │                   │
            ┌──────▼──────┐   ┌────────▼───────┐
            │  LangGraph  │   │  BullMQ Worker │
            │  Agent      │   │  (Node.js)     │
            │  Harness    │   │  Background    │
            │  Orchestrat │   │  job processor │
            │  or routes  │   └────────────────┘
            │  tasks to   │
            │  sub-agents │
            └──────┬──────┘
                   │
     ┌─────────────┼──────────────┐
     ▼             ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────────┐
│Supabase │  │  Redis 7 │  │  Playwright  │
│Postgres │  │  Cache   │  │  Browser     │
│pgvector │  │  BullMQ  │  │  Automation  │
│Storage  │  │  Pub/Sub │  │  (Chromium)  │
│Auth     │  └──────────┘  └──────────────┘
└─────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│  BYOK Model Router                       │
│  Anthropic · OpenAI · Google · Ollama   │
│  NVIDIA NIM                              │
└──────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│  External APIs                           │
│  Hunter.io  ProxyCurl  Exa  Resend      │
└──────────────────────────────────────────┘
```

---

## Layer Details

### 1. Frontend (Next.js 16.2.6 App Router)

**Port:** 3000

| Concern | Technology |
|---|---|
| Framework | Next.js 16.2.6 App Router |
| Language | TypeScript 6 |
| Styling | Tailwind CSS + shadcn/ui |
| State | Zustand 4 (global) + TanStack Query 5 (server state) |
| Animation | Motion (Framer Motion successor) + Three.js |
| Notifications | Sonner toast |
| Auth | `@supabase/ssr` cookie-based sessions |
| HTTP client | Axios with JWT attach middleware |
| Real-time | Server-Sent Events (SSE) via custom `useAgentStream` hook |

**Route groups:**
- `(marketing)/` — public landing, pricing, docs, about
- `(auth)/` — login, register
- `(app)/` — authenticated dashboard (uses `AppShell` layout with sidebar + topbar)

**Auth flow:**
1. User signs in via Supabase Auth (Google OAuth, magic link, email/password)
2. `middleware.ts` refreshes tokens on every request and redirects unauthenticated users
3. Supabase session cookie passed as `Authorization: Bearer <token>` to backend
4. `useUser()` Zustand slice holds decoded user profile

**Agent streaming:**
1. Frontend calls `POST /api/v1/agents/run` → gets `run_id`
2. Opens `GET /api/v1/agents/{run_id}/stream` as SSE
3. `useAgentStream` hook dispatches events to Zustand `agentStore`
4. When agent emits `checkpoint`, `ApprovalModal` renders with action details
5. User approves → `POST /api/v1/agents/{run_id}/approve`

---

### 2. Backend (FastAPI)

**Port:** 8000

| Concern | Technology |
|---|---|
| Framework | FastAPI 0.111+ |
| Language | Python 3.12 |
| ORM | SQLAlchemy 2.0 async |
| Auth | Supabase JWT (HS256) verified in `supabase_auth.py` |
| Rate limit | slowapi (60 req/min per user, 10/min for auth) |
| Encryption | AES-256-GCM, PBKDF2 key derivation (`security.py`) |
| Config | pydantic-settings, all values from env |

**Middleware stack (in order):**
1. CORS (configured for `NEXT_PUBLIC_APP_URL`)
2. JWT verification (extracts `user_id` into request state)
3. slowapi rate limiter
4. Request ID injection

**API structure:**
```
app/api/v1/
├── agents.py        # POST /agents/run · GET /agents/{id}/stream · POST /agents/{id}/approve
├── resume.py        # POST /resume/optimize · GET /resume/download/{id}
├── jobs.py          # GET /jobs/search · GET /jobs/applications · POST /jobs/apply
├── rag.py           # POST /rag/upload · POST /rag/search
├── email.py         # GET /email/threads · POST /email/compose · POST /email/approve/{id}
├── cover_letter.py  # POST /cover-letter/generate
├── interview.py     # POST /interview/session · POST /interview/answer · GET /interview/sessions
├── interview_prep.py # POST /interview-prep/generate
├── company.py       # GET /company/{name}/research
├── salary.py        # POST /salary/benchmark
├── linkedin.py      # POST /linkedin/optimize · POST /linkedin/outreach
├── leads.py         # GET /leads · POST /leads/{id}/action
└── users.py         # GET /users/me · PUT /users/profile · GET/PUT /users/model-settings
```

**Dependency injection (`deps.py`):**
- `get_current_user` — verifies JWT, loads user row from DB
- `get_db` — yields async SQLAlchemy session
- `get_redis` — yields Redis connection from pool

---

### 3. Agent Harness (LangGraph)

All agents are LangGraph graphs with a shared `AgentState` TypedDict. The Orchestrator is a supervisor graph that routes tasks to sub-agents.

**Shared state schema (`state.py`):**
```python
class AgentState(TypedDict):
    user_id: str
    run_id: str
    task: str
    context: dict          # RAG results, user profile, etc.
    messages: list[BaseMessage]
    pending_action: dict | None  # HITL gate
    result: dict | None
    tokens_used: int
    error: str | None
```

**Orchestrator routing:**
```
User task
    ↓
Orchestrator (supervisor)
    ├── "search jobs" → JobSearchAgent
    ├── "optimize resume" → ResumeAgent
    ├── "write cover letter" → CoverLetterAgent
    ├── "optimize LinkedIn" → LinkedInAgent
    ├── "email recruiter" → EmailAgent
    ├── "follow up" → FollowUpAgent
    ├── "mock interview" → InterviewCoachAgent
    ├── "research company" → CompanyResearchAgent
    └── "salary benchmark" → SalaryAgent
```

**SSE event types:**
| Event | Payload | When |
|---|---|---|
| `thinking` | `{step, message}` | Agent reasoning step |
| `tool_call` | `{tool, input}` | Before tool execution |
| `tool_result` | `{tool, output}` | After tool execution |
| `checkpoint` | `{action_type, details}` | HITL approval gate |
| `complete` | `{result}` | Agent finished |
| `error` | `{message}` | Agent failed |

**HITL gate pattern:**
```python
# In any agent, before irreversible action:
yield {"pending_action": {"type": "send_email", "to": ..., "body": ...}}
# Execution pauses — backend stores state in Redis
# User approves via POST /agents/{id}/approve
# Agent resumes with action confirmed
```

**Extended thinking:**
- `thinking.py` wraps Anthropic's `extended_thinking=True` parameter
- Used for cover letters, salary negotiation, complex company research
- Budget: 8,000 thinking tokens by default (configurable)

---

### 4. Data Layer

#### PostgreSQL (Supabase)

| Table | Purpose |
|---|---|
| `auth.users` | Supabase Auth (managed) |
| `public.users` | User profiles, keyed by `supabase_uid` |
| `public.documents` | Uploaded resumes and docs with s3_url |
| `public.applications` | Job application pipeline (kanban state) |
| `public.agent_runs` | Every agent execution: input, output, tokens, duration |
| `public.user_model_settings` | BYOK API keys (encrypted) + active model |
| `public.resume_personas` | Multiple resume versions per user |
| `public.cover_letter_versions` | Versioned cover letters |
| `public.interview_sessions` | Mock interview records + scores |
| `public.salary_reports` | Benchmarking results |
| `public.company_intel` | Cached company research |
| `public.leads` | Recruiter contacts |
| `public.linkedin_outreach_queue` | Outreach campaigns |
| `public.ats_scores` | ATS analysis results |

All tables have RLS policies enforcing `user_id = auth.uid()`.

#### pgvector (RAG)

- Extension: `pgvector 0.7+` with `HNSW` index
- Collections namespaced `{user_id}_{doc_type}` (e.g. `usr_abc_resume`)
- Chunk size: 500 tokens, overlap: 50
- Embedding model: provider-dependent (falls back to `nomic-embed-text` via Ollama for Anthropic/NVIDIA)
- LangChain integration: `langchain-postgres` `PGVector` class

#### Redis

| Usage | Keys |
|---|---|
| Rate limiting | `rate:{user_id}:{minute}` |
| Agent state | `agent:{run_id}:state` |
| SSE pub/sub | `agent:{run_id}:events` channel |
| BullMQ queues | `bull:{queue_name}:*` |
| Response cache | `cache:{hash}` (TTL: 1h) |

#### BullMQ Worker (Node.js)

Separate Node.js process consuming BullMQ queues from Redis. Max 2 concurrent jobs per user.

| Queue | Processor | Trigger |
|---|---|---|
| `job-search` | `job-search.processor.ts` | On-demand via API |
| `daily-search` | `daily-search.processor.ts` | Cron: 8am daily |
| `followup` | `followup.processor.ts` | Day 5 and day 12 post-apply |
| `status-check` | `status-check.processor.ts` | Every 6 hours |

---

## Model Router (BYOK)

All LLM calls go through `llm_gateway.py`. The router:

1. Loads user's `user_model_settings` row from DB
2. Decrypts `api_key_enc` using `APP_SECRET_KEY`
3. Instantiates the appropriate LangChain chat model
4. Wraps with token budget tracking
5. Returns `BaseChatModel` — agents are provider-agnostic

**Provider matrix:**

| Provider | Chat | Embeddings | Special |
|---|---|---|---|
| Anthropic | `claude-sonnet-4-6`, `claude-haiku-4-5` | nomic fallback | Extended thinking |
| OpenAI | `gpt-4o`, `gpt-4o-mini` | `text-embedding-3-small` | — |
| Google | `gemini-2.0-flash`, `gemini-pro` | `embedding-001` | — |
| Ollama | Any local model | `nomic-embed-text` | No API key needed |
| NVIDIA NIM | `llama-3.1-70b-instruct` | nomic fallback | — |

---

## External Integrations

| Service | Used By | Auth |
|---|---|---|
| **Hunter.io** | `EmailAgent`, `LeadsAgent` — find recruiter emails | API key (BYOK optional) |
| **ProxyCurl** | `LinkedInAgent` — LinkedIn profile data | API key (BYOK optional) |
| **Exa** | `CompanyResearchAgent`, `SalaryAgent` — web search | API key (BYOK optional) |
| **Resend** | `ResendService` — transactional email (confirmations) | API key |
| **Gmail API** | `EmailAgent`, `EmailMonitorAgent` — Gmail read/send | Google OAuth (user grants) |
| **Playwright** | `AutoApplyPipeline`, `BrowserControlService` — browser automation | Included (Chromium) |
| **YouTube** | `InterviewPrepAgent` — interview prep videos | API key (optional) |

---

## Data Flow: End-to-End Auto-Apply

```
1. User clicks "Auto Apply" for job posting
2. Frontend: POST /api/v1/agents/run {task: "auto_apply", job_url: "..."}
3. Backend: creates agent_run record, enqueues to BullMQ, opens SSE stream
4. Orchestrator routes to AutoApplyPipeline
5. AutoApplyPipeline:
   a. JobSearchAgent fetches job details (Playwright)
   b. ResumeAgent tailors resume via RAG + LLM → generates PDF
   c. CoverLetterAgent generates cover letter
   d. ATS scores resume → shows to user via SSE
   e. FormFillerService fills application form (Playwright)
   f. HITL gate: checkpoint event → ApprovalModal shows preview
   g. User approves → BrowserControlService submits form
6. ApplicationsService creates/updates applications row (status: submitted)
7. FollowUpAgent schedules day-5 and day-12 emails via BullMQ
8. SSE "complete" event → frontend shows success toast
```

---

## Security Architecture

- **Transport:** TLS 1.2/1.3 only (Nginx), HSTS header
- **Auth:** Supabase JWT (HS256) verified in Python using `SUPABASE_JWT_SECRET` — no round-trip to Supabase on each request
- **Encryption:** API keys AES-256-GCM encrypted before DB write; decrypted only in `llm_gateway.py` at request time
- **RLS:** Every table has `USING (user_id = auth.uid())` policy — DB enforces isolation even if application has a bug
- **Internal routes:** Nginx blocks `GET /internal/*` with `return 404` — worker calls `localhost:8000/internal/` directly
- **Rate limiting:** slowapi on FastAPI, separate Nginx `limit_req_zone` for auth endpoints
- **SAST:** Bandit runs on every CI push; blocks on HIGH severity

---

## Architectural Decisions

| Decision | Chosen | Alternatives Considered | Reason |
|---|---|---|---|
| Agent framework | LangGraph | LangChain LCEL, CrewAI, custom | Supervisor graph + HITL checkpoints built-in |
| Vector store | pgvector | Pinecone, Chroma, Weaviate | Same Postgres instance, no extra service |
| Queue | BullMQ (Node) | Celery (Python), RQ | BullMQ has better UI tooling; worker is lightweight |
| Auth | Supabase Auth | Clerk, Auth.js, custom | RLS integration; managed; multiple providers |
| Browser automation | Playwright/browser-use | Puppeteer, Selenium | Human-like delays built in; Chromium isolation per user |
| PDF generation | ReportLab | WeasyPrint, Puppeteer PDF | Pure Python, no headless browser needed |
| Frontend state | Zustand + TanStack Query | Redux, Jotai | Zustand for global UI; TQ for server state cache |
