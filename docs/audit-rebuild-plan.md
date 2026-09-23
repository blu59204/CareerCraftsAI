# CareerCraft AI — Full Technical Audit & Rebuild Plan

**Generated:** 2026-06-06
**Scope:** End-to-end diagnosis and phased rebuild for a non-functional "AI-vibe-coded" multi-agent platform
**Status:** PLANNING ONLY — No implementation yet

---

## 0. EXECUTIVE SUMMARY

The platform has all the right pieces (15 agents, 31 migrations, 30+ frontend pages, Docker Compose infra) but they're not wired together correctly. The root cause of "nothing works" is a cascade of three critical wiring failures in the agent orchestrator, plus missing environmental validation that prevents any agent from executing.

**Estimated fix difficulty:** Medium — the code is well-structured, the bugs are wiring/data-flow problems, not architectural.

---

## 1. DIAGNOSIS FRAMEWORK

### 1.1 Top 10 Failure Modes (Ranked by Impact)

| # | Failure Mode | Evidence Found | Severity |
|---|---|---|---|
| **1** | **Orchestrator `task` vs `task_type` mismatch** | `AgentState` declares `task`, harness passes `task_type`, `_route_task` reads `state.get("task")` → always END | ❌ CRITICAL |
| **2** | **`auto_apply_agent` import broken** | `orchestrator.py` line imports `AutoApplyAgent` from `app.agents.auto_apply_agent` — file does not exist. Real file is `auto_apply_pipeline.py` exporting a function | ❌ CRITICAL |
| **3** | **Three agents not wired into orchestrator** | `nl_search_agent.py`, `linkedin_outreach_agent.py`, `email_monitor_agent.py` exist but are not in the LangGraph routing table | ❌ CRITICAL |
| **4** | **Missing env vars / misconfigured services** | Backend `.env` has real secrets; worker `.env` minimal; frontend `.env.local` only public keys. No `.env.example` parity check | 🔴 HIGH |
| **5** | **RAG ingestion not triggered** | pgvector extension exists, HNSW indexes present, but no startup validation that collections are populated | 🔴 HIGH |
| **6** | **BullMQ worker not running / no health check** | Worker service in docker-compose.yml has **no health check** — silent death won't be detected | 🔴 HIGH |
| **7** | **RLS blocking backend queries** | RLS enabled on all tables with `FOR ALL TO authenticated`. Backend uses `postgres` role (bypasses RLS) — OK for direct DB but PostgREST calls would fail | 🟡 MEDIUM |
| **8** | **HITL gate never resolving** | Checkpoint SSE events emitted correctly, `/approve` endpoint exists. But if orchestrator doesn't route to agent, no checkpoint is ever generated | 🔴 HIGH (cascade from #1) |
| **9** | **Frontend not consuming SSE** | `useAgentStream` exists in `lib/sse.ts` using `@microsoft/fetch-event-source`. Nginx SSE proxy correct. But if orchestrator doesn't start agents, no events to consume | 🔴 HIGH (cascade from #1) |
| **10** | **pgvector extension disabled** | Backend startup check verifies `vector` extension. 3 HNSW indexes exist. Embedding dimension 1536. | ✅ LOW — likely OK |

### 1.2 Layer-by-Layer Triage Order

```
Layer 1: INFRA     → docker-compose up, health checks, port bindings
Layer 2: AUTH      → Supabase JWT → middleware → get_current_user dependency
Layer 3: DATABASE  → migrations applied, pgvector active, RLS test
Layer 4: BACKEND   → /health returns 200, all routers mounted, agent imports resolve
Layer 5: AGENTS    → orchestrator routes → agent node → LLM call → result
Layer 6: SSE       → event_bus pub/sub → nginx streaming → frontend EventSource
Layer 7: FRONTEND  → auth cookie → API call → SSE hook → Zustand store → render
```

**Fix Layer 1 first.** If infra isn't running, nothing else matters. Then auth, then agents.

---

## 2. BACKEND AUDIT PLAN

### 2.1 FastAPI Startup Checklist

| Item | What to Verify | Fix |
|---|---|---|
| MUST FIX | `config.py` — all 8 required env vars present | Compare `.env` against `.env.example`; add missing vars |
| MUST FIX | `database.py` — asyncpg connects to `DATABASE_URL` | Check connection string format (requires `?connection_limit=20`) |
| MUST FIX | `core/startup` — Redis ping succeeds | Verify `REDIS_URL` format, password in URL |
| MUST FIX | `core/startup` — pgvector extension check | Run `SELECT extname FROM pg_extension WHERE extname='vector'` |
| MUST FIX | `main.py` — all 17 routers registered without import errors | Verify `auto_apply_agent` import fix (see §2.2) |
| VERIFY | Cors origins match `FRONTEND_URL` + `ALLOWED_ORIGINS` | No wildcards allowed in settings |
| VERIFY | `slowapi` rate limiter keyed to user ID | Test with 60+ requests/min |

### 2.2 Agent Harness — Critical Fixes

**FIX A: `orchestrator.py` `_route_task()`**
```python
# File: backend/app/agents/orchestrator.py
# CURRENT (broken):
def _route_task(state: AgentState) -> str:
    task = state.get("task", "")        # ← reads 'task'
    # ... matching logic ...

# FIX: read 'task_type' instead:
def _route_task(state: AgentState) -> str:
    task = state.get("task_type", state.get("task", ""))  # ← compat with both
```

**FIX B: `orchestrator.py` auto_apply import**
```python
# File: backend/app/agents/orchestrator.py
# CURRENT (broken):
from app.agents.auto_apply_agent import AutoApplyAgent
# FIX:
from app.agents.auto_apply_pipeline import run_auto_apply_pipeline
# And wrap as a callable node function
```

**FIX C: Wire missing agents**
| Agent File | Node Name | Keyword(s) |
|---|---|---|
| `nl_search_agent.py` | `nl_search` | `nl_search`, `natural_language_search` |
| `linkedin_outreach_agent.py` | `linkedin_outreach` | `linkedin_outreach`, `connect` |
| `email_monitor_agent.py` | `email_monitor` | `email_monitor`, `check_inbox` |

**FIX D: Validate `AgentState` completeness**
| Field | TypedDict | Harness passes | Orchestrator reads | OK? |
|---|---|---|---|---|
| `user_id` | ✅ | ✅ | ✅ | ✅ |
| `run_id` | ✅ | ✅ | ✅ | ✅ |
| `task` | ✅ String | **Passes as `task_type`** | Reads `task` | ❌ |
| `context` | ✅ dict | ✅ | ✅ | ✅ |
| `messages` | ✅ list[dict] | ✅ | ✅ | ✅ |
| `pending_action` | ✅ dict\|None | ✅ | ✅ | ✅ |
| `result` | ✅ dict\|None | ✅ | ✅ | ✅ |
| `tokens_used` | ✅ int | ✅ | ✅ | ✅ |
| `error` | ✅ str\|None | ✅ | ✅ | ✅ |

**Single fix needed: rename `task` → `task_type` in `state.py` TypedDict, OR rename harness construction field. Recommend: use `task_type` everywhere (more descriptive, matches harness).**

### 2.3 LLM Gateway Verification

| Item | What to Check | Status |
|---|---|---|
| MUST FIX | `model_router.py` `_build_llm()` — 7 providers supported | Code present, match/case correct |
| MUST FIX | `security.py` `decrypt_api_key()` — PBKDF2 + AES-256-GCM | Code correct. Note: salt is first 16 bytes of ciphertext, not a separate column |
| VERIFY | Token tracking callback fires on every LLM call | `TokenTrackingCallback` attached in `_build_llm()` |
| VERIFY | Key redaction callback redacts 9 API key patterns | `KeyRedactionCallback` attached |
| NICE TO HAVE | `user_model_settings` has no `token_budget` column | Add migration for per-user budget limits per AGENTS.md |

### 2.4 SSE Verification

| Item | What to Check | Status |
|---|---|---|
| MUST FIX | `event_bus.py` — dedicated publisher thread alive | Daemon thread, `run_coroutine_threadsafe` — correct pattern |
| VERIFY | `stream_events()` — async generator yields proper SSE format | `event: {type}\ndata: {json}\n\n` format confirmed |
| VERIFY | Nginx `proxy_buffering off` on stream routes | ✅ Confirmed in `nginx.conf.template` |
| VERIFY | Nginx `proxy_read_timeout 300s` | ✅ Confirmed |
| VERIFY | Keepalive ping every 5s | ✅ In `stream_events()` |
| NICE TO HAVE | SSE auto-termination on agent complete/error | ✅ In `stream_events()` |

### 2.5 HITL Gate Verification

| Item | What to Check | Status |
|---|---|---|
| MUST FIX | Agent sets `status="awaiting_approval"` + `pending_action` | Resume, CoverLetter, LinkedIn, Email, Salary, AutoApply do this |
| VERIFY | Orchestrator emits `"checkpoint"` SSE on `awaiting_approval` | ✅ In `_node_runner()` — but only if orchestrator routes to agent (blocked by FIX A) |
| VERIFY | `POST /agents/{run_id}/approve` reads and resumes | ✅ Endpoint exists in `agents.py` |
| VERIFY | `POST /email/approve/{run_id}` actually sends via Gmail | ✅ Endpoint exists in `email.py` |
| VERIFY | Redis state store persists across approval cycle | `agent:{run_id}:state` key pattern — verify |

### 2.6 BullMQ Worker Verification

| Item | What to Check | Status |
|---|---|---|
| MUST FIX | Worker has no health check in docker-compose.yml | Add `healthcheck` block |
| VERIFY | Worker connects to `agent-queue` on startup | ✅ In `worker/src/index.ts` |
| VERIFY | 4 processors registered: `job-search`, `followup-email`, `status-check`, `daily-search` | ✅ |
| VERIFY | Cron: status-check every 6h, daily-search every 24h | ✅ |
| VERIFY | Internal calls use `INTERNAL_SECRET` header | ✅ |
| VERIFY | 2 concurrent jobs, 10/min rate limit | ✅ |

---

## 3. DATABASE AUDIT PLAN

### 3.1 Migration Status

| # | Migration | Table/Feature | Status |
|---|---|---|---|
| 0001 | create_users | `users` table + uuid-ossp | VERIFY applied |
| 0002 | create_model_settings | `user_model_settings` | VERIFY applied |
| 0003 | create_documents | `user_documents` | VERIFY applied |
| 0004 | create_applications | `job_applications` | VERIFY applied |
| 0005 | create_leads | `leads` | VERIFY applied |
| 0006 | create_agent_runs | `agent_runs` | VERIFY applied |
| 0007 | create_pgvector_indexes | `vector` extension | VERIFY applied |
| 0008 | enable_rls | Initial RLS (Clerk) | Superceded by 0018/0028 |
| 0009 | clerk_to_supabase | Auth migration | VERIFY applied |
| 0010 | user_preferences | `user_preferences` | VERIFY applied |
| 0011 | cover_letter_versions | `cover_letter_versions` | VERIFY applied |
| 0012 | interview_sessions | `interview_sessions` | VERIFY applied |
| 0013 | salary_reports | `salary_reports` | VERIFY applied |
| 0014 | company_intel | `company_intel` | VERIFY applied |
| 0015 | resume_personas | `resume_personas` | VERIFY applied |
| 0016 | linkedin_outreach_queue | `linkedin_outreach_queue` | VERIFY applied |
| 0017 | ats_scores | `ats_scores` | VERIFY applied |
| 0018 | fix_rls_supabase_uid | RLS fix | VERIFY applied |
| 0019 | linkedin_credentials_auto_mode | Encrypted creds | VERIFY applied |
| 0020 | fix_frontend_dashboard_schema_drift | Schema alignment | VERIFY applied |
| 0021 | google_oauth_tokens | OAuth tokens | VERIFY applied |
| 0022 | job_application_location | `location` column | VERIFY applied |
| 0023 | secure_post_rls_tables | Agent memory RLS | VERIFY applied |
| 0024 | rls_with_check_core_tables | Core-6 WITH CHECK | VERIFY applied |
| 0025 | hnsw_index_embeddings | HNSW on langchain_pg_embedding | VERIFY applied |
| 0026 | ensure_feature_and_memory_tables | Catch-up tables | VERIFY applied |
| 0027 | signup_profile_metadata | Signup trigger | VERIFY applied |
| 0028 | clerk_third_party_auth_rls | Final RLS pattern | VERIFY applied |
| 0029 | user_preferences_years_experience_check | CHECK constraint | VERIFY applied |
| 0030 | enable_rls_public_tables | Lock down LangChain tables | VERIFY applied |
| 0031 | user_preferences_prefer_live_browser | `prefer_live_browser` flag | VERIFY applied |

**Verification command:** `supabase db dump --local --data-only | grep -c "migrations"` or check `supabase_migrations.schema_migrations` table.

### 3.2 RLS Policy Audit

**Canonical pattern** (from migration 0028):
```sql
USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
```

| Table | RLS Enabled | Owner Policy | WITH CHECK | Status |
|---|---|---|---|---|
| `users` | ✅ | `supabase_uid = auth.jwt()->>'sub'` | ✅ | VERIFY |
| `user_model_settings` | ✅ | ✅ | ✅ | VERIFY |
| `user_documents` | ✅ | ✅ | ✅ | VERIFY |
| `job_applications` | ✅ | ✅ | ✅ | VERIFY |
| `leads` | ✅ | ✅ | ✅ | VERIFY |
| `agent_runs` | ✅ | ✅ | ✅ | VERIFY |
| `user_preferences` | ✅ | ✅ | ✅ | VERIFY |
| `cover_letter_versions` | ✅ | ✅ | ✅ | VERIFY |
| `interview_sessions` | ✅ | ✅ | ✅ | VERIFY |
| `salary_reports` | ✅ | ✅ | ✅ | VERIFY |
| `company_intel` | ✅ | ✅ | ✅ | VERIFY |
| `resume_personas` | ✅ | ✅ | ✅ | VERIFY |
| `linkedin_outreach_queue` | ✅ | ✅ | ✅ | VERIFY |
| `ats_scores` | ✅ | ✅ | ✅ | VERIFY |
| `user_memories` | ✅ | ✅ | ✅ | VERIFY |
| `agent_episodes` | ✅ | ✅ | ✅ | VERIFY |
| `agent_memory_*` (4 tables) | ✅ | ✅ (user_id TEXT, `id::text` cast) | ✅ | VERIFY |
| LangChain tables | ✅ | No policy (backend bypasses via `postgres`) | N/A | VERIFY |

### 3.3 pgvector Health Check

| Item | Command | Status |
|---|---|---|
| MUST FIX | Extension enabled | `SELECT extname FROM pg_extension WHERE extname='vector'` | VERIFY |
| MUST FIX | HNSW on `langchain_pg_embedding` | `SELECT * FROM pg_indexes WHERE indexname='idx_langchain_embedding_hnsw'` | VERIFY |
| MUST FIX | HNSW on `user_memories` | Check `user_memories_hnsw` | VERIFY |
| MUST FIX | HNSW on `agent_episodes` | Check `agent_episodes_hnsw` | VERIFY |
| VERIFY | Dimension 1536 on all embedding columns | Check column types | VERIFY |
| NICE TO HAVE | RAGService checks collection exists before `retrieve()` | Current code has no existence check — add `collection_exists()` guard | VERIFY |

### 3.4 Schema Alignment with AGENTS.md

| AGENTS.md Claim | Actual Schema | Match? |
|---|---|---|
| `user_model_settings.api_key_enc` (TEXT) | ✅ `api_key_enc TEXT` | ✅ |
| `user_model_settings.api_key_salt` (TEXT) | ❌ **Not present** — salt embedded in ciphertext prefix | ⚠️ Doc mismatch, functionally OK |
| `agent_runs.status` CHECK (running, awaiting_approval, completed, failed) | ✅ Exact match | ✅ |
| `agent_runs.input` (JSONB) | ✅ | ✅ |
| `agent_runs.output` (JSONB) | ✅ | ✅ |
| `agent_runs.tokens_used` (INTEGER) | ✅ | ✅ |
| `agent_runs.duration_ms` (INTEGER) | ✅ | ✅ |

---

## 4. FRONTEND AUDIT PLAN

### 4.1 Auth Flow Verification

| Step | What to Verify | Status |
|---|---|---|
| MUST FIX | `middleware.ts` calls `updateSession()` from `@supabase/ssr` | ✅ Present at `frontend/src/middleware.ts` |
| MUST FIX | Auth callback at `/auth/callback/route.ts` | ✅ Present |
| VERIFY | JWT attached via Axios interceptor | Check `lib/api.ts` — `api.interceptors.request.use()` |
| VERIFY | `get_current_user` dependency on backend reads JWT correctly | `supabase_auth.py` uses `jwt.decode()` with `verify_aud=False` — verify this is intentional |
| VERIFY | Token refresh on expiry | `middleware.ts` `updateSession` handles this |

### 4.2 SSE Hook Audit (`lib/sse.ts`)

| Item | What to Verify | Status |
|---|---|---|
| MUST FIX | Uses `@microsoft/fetch-event-source` for streaming | ✅ Confirmed |
| VERIFY | Auto-reconnect on connection loss | ✅ `fetchEventSource` has built-in retry |
| VERIFY | Event dispatch to Zustand `agentStore` | Check `agentSlice.ts` for `addSSEEvent` action |
| VERIFY | Checkpoint events render `ApprovalModal` | Check `components/agents/ApprovalModal.tsx` |
| MUST FIX | Hook must be in `'use client'` component | Next.js App Router cannot consume SSE in server components |
| VERIFY | SSE endpoint URL: `/api/v1/agents/{runId}/stream` | Matches nginx location block |

### 4.3 TanStack Query Audit

| Item | What to Verify | Status |
|---|---|---|
| VERIFY | Query invalidation after agent completes | Check if agent pages call `queryClient.invalidateQueries()` on SSE `complete` event |
| VERIFY | Stale time configuration | Check `QueryClient` default options in `Providers.tsx` |
| NICE TO HAVE | Optimistic updates on approval | Current pattern unknown |

### 4.4 Route Groups Audit

| Route Group | Pages | Layout | Status |
|---|---|---|---|
| `(app)/` | 12 feature pages + onboarding + settings | `AppShell` with sidebar + topbar | VERIFY |
| `(auth)/` | login, register | Auth layout | VERIFY |
| `(marketing)/` | about, contact, docs, pricing, privacy, status, terms | Marketing layout | VERIFY |
| `auth/callback/` | route.ts + client page | None | VERIFY |
| `sso-callback/` | page.tsx | None | VERIFY |

### 4.5 UI Component Audit

| Item | What to Check | Status |
|---|---|---|
| VERIFY | shadcn/ui component imports from `@/components/ui/*` | 22 components present |
| VERIFY | `'use client'` on all interactive components | Spot-check `ApprovalModal`, `ApplicationKanban`, agent pages |
| VERIFY | Tailwind class conflicts | Check for conflicting `flex`/`grid` or duplicate color classes |
| VERIFY | Three.js canvas sizing | `ImmersiveCanvas` — check `resize` handler and `dpr` cap |
| NICE TO HAVE | Dark mode default | `class="dark"` in root layout or `ThemeProvider` defaultTheme |

---

## 5. UI/UX REDESIGN PRIORITIES

### 5.1 Five Most Impactful Pages (Fix Order)

| Priority | Page | Why |
|---|---|---|
| **P0** | **Dashboard** (`(app)/dashboard`) | First thing users see. Needs agent activity feed + KPI cards (applications sent, interviews, response rate). Currently stub. |
| **P1** | **Agent Activity** (`(app)/agents`) | SSE live stream panel — users need to see agents working. Hook exists but page is likely non-functional. |
| **P2** | **Job Search** (`(app)/jobs`) | Results grid with match score badges. Core value prop. |
| **P3** | **Applications Kanban** (`(app)/applications`) | Drag-and-drop pipeline. Differentiator. `ApplicationKanban` component exists. |
| **P4** | **Resume Editor** (`(app)/resume`) | ATS score sidebar with keyword coverage. `ResumeScoreCard`, `AtsScoreRing`, `KeywordCoverage` components exist. |
| **P5** | **ApprovalModal** (`components/agents/ApprovalModal`) | Every HITL interaction goes through this. Must show full action preview, diff view for edited content, approve/cancel with loading state. |

### 5.2 Design System Specification

| Token Category | Values |
|---|---|
| **Spacing scale** | 4px base: 4, 8, 12, 16, 24, 32, 48, 64, 96 |
| **Color — Dark (default)** | `--background: 222.2 84% 4.9%`, `--foreground: 210 40% 98%`, `--primary: 217.2 91.2% 59.8%` (blue), `--accent: 262.1 83.3% 57.8%` (purple — CareerCraft brand) |
| **Color — Light** | Invert background/foreground, adjust saturation |
| **Border radius** | sm: 0.375rem, md: 0.5rem, lg: 0.75rem, xl: 1rem |
| **Typography ramp** | font-sans: Inter, font-mono: JetBrains Mono. Sizes: xs(12), sm(14), base(16), lg(18), xl(20), 2xl(24), 3xl(30), 4xl(36) |
| **Component hierarchy** | Page → Section → Card → Widget. Use `Card` from shadcn/ui as the base container. |

### 5.3 ApprovalModal Redesign Spec

```
┌─────────────────────────────────────────────────────┐
│  [Agent Icon] ResumeAgent — Resume Ready for Review  │
├─────────────────────────────────────────────────────┤
│                                                       │
│  ┌─────────────────┐  ┌─────────────────────────────┐│
│  │   ATS Score: 84  │  │  Preview:                  ││
│  │   [Donut Chart]  │  │  [Rendered resume preview] ││
│  │                  │  │                             ││
│  │  Keywords: 12/15 │  │                             ││
│  └─────────────────┘  └─────────────────────────────┘│
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Changes Made: [Diff view toggle]               │ │
│  │  + Added: "Kubernetes" keyword                   │ │
│  │  ~ Modified: Summary paragraph                   │ │
│  │  - Removed: Outdated role                       │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  [Cancel]  [Edit & Approve]  [Approve & Send ✓]       │
│              (loading)                                 │
└─────────────────────────────────────────────────────┘
```

---

## 6. PHASED REBUILD ROADMAP

### Phase 0: Environment Triage

**Goal:** All services running, `/health` returns 200

| Step | Action | File(s) |
|---|---|---|
| P0-1 | Copy `.env.example` to `.env`, fill all 8 required vars | `backend/.env` |
| P0-2 | Run `docker-compose up -d redis` → verify `redis-cli -a $REDIS_PASSWORD ping` returns PONG | `docker-compose.yml` |
| P0-3 | Run `supabase db push` or `supabase migration up` to apply all 31 migrations | `supabase/` |
| P0-4 | Verify pgvector: `SELECT extname FROM pg_extension WHERE extname='vector'` | DB |
| P0-5 | Start backend: `uvicorn app.main:app --reload` → hit `GET /health` | `backend/` |
| P0-6 | Verify all 17 routers mount without import errors | `backend/app/main.py` |
| P0-7 | Start frontend: `npm run dev` → verify localhost:3000 loads without console errors | `frontend/` |
| P0-8 | Start worker: verify it connects to Redis and registers processors | `worker/` |

### Phase 1: Core Auth + RAG

**Goal:** Supabase JWT flow working end-to-end, document upload → pgvector ingestion → semantic search

| Step | Action | File(s) |
|---|---|---|
| P1-1 | Fix `supabase_auth.py` JWT verification — confirm audience=`authenticated`, HS256 algorithm | `backend/app/core/supabase_auth.py` |
| P1-2 | Test auth flow: register → login → get JWT → call `GET /api/v1/users/me` → 200 | `frontend/src/lib/supabase.ts`, `middleware.ts` |
| P1-3 | Fix Axios interceptor to attach JWT on every request | `frontend/src/lib/api.ts` |
| P1-4 | Verify `RAGService.ingest()` works: upload PDF → chunks created → embeddings stored | `backend/app/services/rag_service.py` |
| P1-5 | Verify `RAGService.retrieve()` returns top-k chunks with scores | Same file |
| P1-6 | Add collection existence check before `retrieve()` | `backend/app/services/rag_service.py` |

### Phase 2: First Agent Live (ResumeAgent)

**Goal:** ResumeAgent returning output via SSE, ApprovalModal rendering

| Step | Action | File(s) |
|---|---|---|
| P2-1 | **FIX orchestration**: rename `AgentState.task` → `task_type` in TypedDict | `backend/app/agents/state.py` |
| P2-2 | **FIX orchestration**: update `_route_task` to read `state.get("task_type")` | `backend/app/agents/orchestrator.py` |
| P2-3 | **FIX orchestration**: fix `auto_apply_agent` import → `auto_apply_pipeline` | `backend/app/agents/orchestrator.py` |
| P2-4 | Wire `nl_search_agent`, `linkedin_outreach_agent`, `email_monitor_agent` into routing table | `backend/app/agents/orchestrator.py` |
| P2-5 | Test ResumeAgent: call `POST /api/v1/agents/run` with task_type=`tailor_resume` | `backend/app/api/v1/agents.py` |
| P2-6 | Verify SSE stream: `GET /api/v1/agents/{runId}/stream` → see `thinking`, `checkpoint`, `complete` events | `backend/app/core/event_bus.py` |
| P2-7 | Verify `useAgentStream` hook receives events and updates `agentStore` | `frontend/src/lib/sse.ts`, `frontend/src/store/agentSlice.ts` |
| P2-8 | Verify `ApprovalModal` renders on `checkpoint` event | `frontend/src/components/agents/ApprovalModal.tsx` |
| P2-9 | Test approve flow: click Approve → `/agents/{run_id}/approve` → agent resumes → `complete` | `backend/app/api/v1/agents.py` |

### Phase 3: UI Rebuild

**Goal:** All 12 dashboard pages properly laid out, design system applied

| Step | Action | File(s) |
|---|---|---|
| P3-1 | Audit all pages for `'use client'` correctness — server components can't use hooks/SSE/browser APIs | All `frontend/src/app/(app)/**/page.tsx` |
| P3-2 | Build Dashboard: KPI cards (applications, interviews, response rate, active agents) + agent activity feed | `frontend/src/app/(app)/dashboard/page.tsx` |
| P3-3 | Build Agents page: live SSE stream panel + agent run history | `frontend/src/app/(app)/agents/page.tsx` |
| P3-4 | Build Job Search: search form + results grid with `JobMatchCard` badges | `frontend/src/app/(app)/jobs/page.tsx` |
| P3-5 | Build Applications: `ApplicationKanban` drag-and-drop pipeline | `frontend/src/app/(app)/applications/page.tsx` |
| P3-6 | Build Resume Editor: text area + `AtsScoreRing` + `KeywordCoverage` sidebar | `frontend/src/app/(app)/resume/page.tsx` |
| P3-7 | Apply design system tokens (Tailwind config already has custom colors — verify they render) | `frontend/tailwind.config.ts` |
| P3-8 | Fix Three.js canvas: check `ImmersiveCanvas` resize handler, cap `dpr` at 2 for performance | `frontend/src/components/immersive/ImmersiveCanvas.tsx` |

### Phase 4: All Agents Wired + BullMQ

**Goal:** All 15 agents functional, crons running, HITL tested

| Step | Action | File(s) |
|---|---|---|
| P4-1 | Verify all 15 agent nodes return correct `AgentState` dict | All `backend/app/agents/*.py` |
| P4-2 | Test EmailAgent with HITL: draft email → checkpoint → approve → Gmail send | `backend/app/agents/email_agent.py`, `email.py` |
| P4-3 | Test AutoApplyPipeline with both HITL checkpoints | `backend/app/agents/auto_apply_pipeline.py` |
| P4-4 | Add health check to worker in docker-compose.yml | `docker-compose.yml` |
| P4-5 | Start worker: verify `agent-queue` connects, all 4 processors register | `worker/src/index.ts` |
| P4-6 | Test BullMQ cron: trigger `status-check` manually → verify backend callback | `worker/src/processors/status-check.processor.ts` |
| P4-7 | Test RLS: verify a user cannot read another user's applications | DB test |
| P4-8 | End-to-end test: upload resume → search jobs → tailor resume → apply → receive follow-up email |

### Phase 5: Security Hardening + Tests

**Goal:** Bandit SAST clean, all 46 tests passing

| Step | Action | File(s) |
|---|---|---|
| P5-1 | Run `bandit -r backend/app/` — fix all HIGH/MEDIUM findings | CI |
| P5-2 | Verify `constraints.txt` blocks `langgraph-checkpoint-sqlite==0.0.0` (CVE-2025-67644) | `backend/constraints.txt` |
| P5-3 | Verify browser-use URL is reachable from backend container | `docker-compose.yml` network |
| P5-4 | Run all 40 unit tests: `pytest backend/tests/unit/ -v` | CI |
| P5-5 | Run 6 security tests: `pytest backend/tests/security/ -v` | CI |
| P5-6 | Run integration tests with `INTEGRATION=1` flag (requires live DB) | CI |
| P5-7 | Verify no secrets in committed `.env` files | `.gitignore` check |

---

## 7. RISK FLAGS

| Risk | Details | Mitigation |
|---|---|---|
| **Browser Use library** | `BROWSER_USE_OLLAMA_URL` must be reachable. If Browser Use is not running, AutoApplyPipeline will fail at form-filling step | Verify with `curl $BROWSER_USE_OLLAMA_URL/health` before Phase 4 |
| **LangGraph CVE** | `langgraph-checkpoint-sqlite` must be blocked. Currently in `constraints.txt` as `0.0.0` | Verify `pip list \| grep langgraph-checkpoint` shows no installation |
| **Supabase JWT audience** | `supabase_auth.py` uses `verify_aud=False` — this bypasses audience check. Verify it's intentional or fix to `audience="authenticated"` | Audit `backend/app/core/supabase_auth.py` |
| **SSE + Next.js** | `useAgentStream` must be called in `'use client'` component. Server components can't consume EventSource | Audit all pages importing `useAgentStream` |
| **pgvector collections** | `RAGService.retrieve()` called before collections exist = error | Add `collection_exists()` guard in `rag_service.py` |
| **Docker health checks** | Worker and Nginx have no health checks — silent failures won't auto-restart | Add health checks in Phase 4 |
| **`.env` secrets in repo** | `backend/.env` contains real credentials | Verify `.gitignore` includes `.env` (not just `.env.local`). Add pre-commit hook. |
| **`task` vs `task_type`** | The single largest bug in the system — blocks ALL agent execution | Phase 2, P2-1 |

---

## 8. VERIFICATION CHECKLIST

After each phase, run these checks before proceeding:

### Phase 0 Verification
```
[ ] docker-compose ps — all 5 services healthy
[ ] curl localhost:8000/health → {"status":"ok","db":"ok","redis":"ok","version":"1.0.0"}
[ ] curl localhost:3000 → HTML response (no JS errors in console)
[ ] supabase migration list — all 31 applied
[ ] SELECT extname FROM pg_extension WHERE extname='vector' → 1 row
```

### Phase 1 Verification
```
[ ] Login via frontend → JWT in cookies → GET /api/v1/users/me → 200
[ ] Upload PDF → chunks in langchain_pg_embedding → HNSW search returns results
[ ] Semantic search: POST /api/v1/rag/search → relevant chunks returned
```

### Phase 2 Verification
```
[ ] POST /api/v1/agents/run — ResumeAgent → returns run_id
[ ] GET /api/v1/agents/{run_id}/stream → SSE events: thinking, checkpoint, complete
[ ] ApprovalModal renders with approve/cancel buttons
[ ] POST /agents/{run_id}/approve → agent resumes → complete event
[ ] AgentRun record in DB with status='completed', tokens_used > 0, duration_ms > 0
```

### Phase 3 Verification
```
[ ] All 12 feature pages load without console errors
[ ] Dashboard shows KPI cards with real data
[ ] JobSearch page shows results grid
[ ] ApplicationKanban supports drag-and-drop
[ ] Dark mode works across all pages
```

### Phase 4 Verification
```
[ ] All 15 agent types execute successfully
[ ] EmailAgent → checkpoint → approve → email sent via Gmail API
[ ] AutoApplyPipeline → both checkpoints → application submitted
[ ] BullMQ status-check runs every 6h
[ ] RLS: user A cannot read user B's data
```

### Phase 5 Verification
```
[ ] bandit -r backend/app/ → 0 HIGH, 0 MEDIUM
[ ] pytest backend/tests/unit/ -v → 40 passed
[ ] pytest backend/tests/security/ -v → 6 passed
[ ] No .env files in git tracking
```
