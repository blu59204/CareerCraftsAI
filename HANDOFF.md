# COMPLETE HANDOFF DOCUMENT — CareerCraft AI
**Date:** 2026-09-06
**Prepared for:** Brand-new AI assistant with zero context
**Working directory:** `D:\CareerCraft AI`

---

## 1. PROJECT OVERVIEW

### What it is
**CareerCraft AI** (also called **CareerCraftsAI** in repo/folders, and **JobAgent AI** in older docs/PRD) is a full-stack, multi-agent job-search automation platform.

What it's supposed to do — 15 LangGraph agents coordinated by a supervisor:
1. **Orchestrator** — LangGraph supervisor, routes tasks, streams live progress via SSE
2. **JobSearchAgent** (`backend/app/agents/job_search.py`) — searches LinkedIn, Indeed, Naukri, Shine, Freshersworld, Glassdoor via Playwright/browser-use + APIs, scores matches 0-100
3. **ResumeAgent** (`resume_agent.py`) — RAG-powered resume tailoring to a JD, ATS scoring, PDF generation
4. **CoverLetterAgent** — personalized cover letters, uses Claude extended thinking
5. **LinkedInAgent** — rewrites headline, About, top-3 experience bullets
6. **LinkedInOutreachAgent** — finds recruiter emails (Hunter.io, ProxyCurl), drafts connection requests/InMails
7. **EmailAgent** — reads Gmail threads, drafts recruiter outreach
8. **FollowUpAgent** — schedules day-5 and day-12 follow-ups, auto-cancels on reply. NOTE: NOT a LangGraph node — `schedule_followups()` called directly from `internal.py`
9. **EmailMonitorAgent** — monitors inbox every 6h via BullMQ `status-check`, surfaces action items
10. **InterviewCoachAgent** — live mock interviews, scores clarity/relevance/depth 0-10
11. **InterviewPrepAgent** — question banks + study guides (Exa + YouTube optional)
12. **CompanyResearchAgent** — culture, financials, news, interview process, key people; cached 7 days in `company_intel`
13. **SalaryAgent** — p25/p50/p75/p90 benchmarks + negotiation script, extended thinking
14. **NLSearchAgent** — plain-English query → structured search → delegates to JobSearchAgent
15. **AutoApplyPipeline** — end-to-end: fetch JD → tailor resume → cover letter → ATS score → HITL checkpoint → fill form → HITL checkpoint → submit → create application record → schedule follow-ups
16. **RAG/Memory** (not standalone) — `backend/app/services/rag_service.py` + `backend/app/agents/memory/` — pgvector ingest/retrieve for all agents

> Every email send or application submit requires explicit human approval (HITL checkpoint via SSE `checkpoint` event + `POST /approve`). Enforced server-side.

### Who it's for + main goal
For job seekers (India + international). Main goal: automate entire job search while user keeps control. **BYOK model:** user brings own AI API key (Anthropic/OpenAI/Google/Ollama/NVIDIA NIM). User pays only own AI usage. Data stays in user's Supabase.

### Names
- App name: **CareerCraft AI** (README title)
- Repo name: **CareerCraftsAI** (folder `D:\CareerCraft AI`, git remote `https://github.com/blu59204/CareerCraftsAI.git`)
- Old code name: **JobAgent AI** (used in `CareerCraft AI.md` PRD, `CLAUDE.md`, `worker` package `jobagent-worker`, frontend package `jobagent-frontend`)
- PRD file: `CareerCraft AI.md` + `JobAgent_AI_PRD.md` (authoritative for product decisions)

---

## 2. TECH STACK

### OS / Environment (current user)
- **OS:** `win32` (Windows)
- **Shell:** Windows PowerShell 5.1
- **Workspace root:** `D:\CareerCraft AI` (is a git repo, branch `master`)
- **Temp dir approved for outside-workspace work:** `C:\Users\badbo\AppData\Local\Temp\opencode`
- PowerShell notes: chain with `cmd1; if ($?) { cmd2 }`, NOT `&&`. Use `workdir` param instead of `cd`. Quote paths with spaces.

### Backend — exact versions
- **Language:** Python 3.12 (verified: `backend/Dockerfile:1` `FROM python:3.12-slim`, `pyproject.toml` `requires-python >=3.12`, `ruff/black target py312`)
- **Framework:** FastAPI `>=0.111.0`, Uvicorn `[standard] >=0.30.1`, `python-multipart`, `email-validator`
- **DB ORM:** SQLAlchemy `[asyncio] >=2.0.30`, `asyncpg >=0.30.0`, `alembic >=1.13.1`, `pgvector >=0.3.2`
- **Supabase:** `supabase >=2.30.0`, `langchain-postgres >=0.0.17`, `psycopg[binary] >=3.3.4`
- **Agents (pinned in `backend/constraints.txt` — wins over `requirements.txt`):**
  ```
  langgraph==0.2.76
  langchain-core==0.3.86
  langchain==0.3.30
  langchain-anthropic==0.3.22
  langchain-openai==0.3.35
  langchain-google-genai==2.1.12
  langchain-ollama==0.3.10
  langchain-community==0.3.31
  langchain-google-community==2.0.10
  langgraph-checkpoint-sqlite==0.0.0  # blocked — PostgreSQL checkpoints only
  ```
  Reason: orchestrator uses `0.2.x` APIs (`set_conditional_entry_point`, `StateGraph.compile`). CVE-2025-68664 patched via `langchain-core 1.4.0` claim in README vs pinned `0.3.86` in constraints — verify. CVE-2025-67644 blocked via constraints.
- **Special Dockerfile case:** `browser-use==0.12.9` installed with `--no-deps`, then deps minus `markdownify` so `python-jobspy`'s markdownify wins. `playwright install chromium` + ~20 apt libs.
- **Other:** `pydantic>=2.7.4`, `pydantic-settings>=2.3.0`, `python-jose[cryptography]>=3.3.0`, `cryptography>=42.0.8`, `slowapi>=0.1.9` (rate limit 60 req/min/user), `redis>=5.0.0`, `bullmq>=2.25.0`, `httpx>=0.27.0`, `resend>=0.8.0`, `youtube-search-python`, `pymupdf>=1.24.0`, `python-docx>=1.1.0`, `reportlab>=4.2.0` (PDF), `pypdf>=6.0.0`, `python-jobspy>=1.1.75`, `playwright>=1.44.0`, `agentql`, `cdp-use`, `bubus`, `browser-use-sdk`, `google-api-python-client`, `posthog`, `uuid7`, `psutil`
- **Dev:** `pytest>=8.2.0`, `pytest-asyncio`, `pytest-mock`, `hypothesis`, `bandit>=1.7.8`, `ruff>=0.4.0`, `black>=24.0.0`, `coverage`

### Frontend — exact versions (from `frontend/package.json`, installed verified)
```
next ^16.2.6 (installed 16.2.6) — README says Next.js 14, DRIFT: actually 16.2.6
react ^19.2.6, react-dom ^19.2.6
typescript ^6.0.3
tailwindcss ^3.4.17, autoprefixer ^10.4.20, postcss ^8.4.49
zustand ^5.0.13
axios ^1.16.1
@tanstack/react-query ^5.100.14 + devtools
@supabase/supabase-js ^2.106.2, @supabase/ssr ^0.10.3, @supabase/auth-helpers-nextjs ^0.15.0
@microsoft/fetch-event-source ^2.0.1
@react-three/fiber ^9.6.1, @react-three/drei ^10.7.7, three ^0.181.2
motion ^12.40.0 (Framer Motion successor)
next-themes ^0.4.6, lucide-react ^1.17.0, sonner ^2.0.7, dompurify ^3.4.7
clsx, tailwind-merge, class-variance-authority
9x @radix-ui/* (accordion/dialog/label/select/scroll-area/separator/slot/switch/tabs/avatar)
```
Dev: `@types/react ^19.2.15`, `@types/node ^25.9.1`, `eslint ^9.39.4`, `eslint-config-next ^16.2.6`
Docker: `FROM node:24-alpine` multi-stage (`builder: npm ci + build`, `runner: .next/standalone`, `CMD ["node","server.js"]`)
`tsconfig`: `strict:true`, `target:ES2017`, `jsx:react-jsx`, `paths @/* -> ./src/*`
`next.config.js`: `output:standalone`, `rewrites /api/v1/:path* -> ${BACKEND_URL}/api/v1/:path*` (default `http://backend:8000`), images `avif,webp` + `https://i.ytimg.com`

### Worker
- `worker/package.json` `jobagent-worker@0.1.0`: `bullmq ^5.77.6`, `ioredis ^5.11.0`, `axios ^1.16.1`, `typescript ^6.0.3`, `ts-node ^10.9.2`
- Scripts: `build: tsc`, `start: node dist/index.js`, `dev: node --env-file=.env -r ts-node/register src/index.ts`
- Processors: `job-search`, `followup`, `daily-search`, `status-check` (every 6h)

### Database / Services / Hosting / Tools
- **DB:** Supabase Cloud — PostgreSQL 16 + pgvector 0.7+ + Storage + Auth. 32 migrations in `supabase/migrations/` (0001-0032, see §3). HNSW indexes required for prod scale.
- **Cache/Queue:** Redis 8-alpine (`redis:8-alpine`), `--appendonly yes --maxmemory 512mb --maxmemory-policy noeviction --requirepass ${REDIS_PASSWORD:-changeme}`
- **Hosting:** Hybrid — Supabase Cloud (managed) + Docker Compose on VPS for app logic. Nginx (TLS 1.2/1.3 + security headers, `nginx/nginx.conf.template`, `${DOMAIN}` envsubst). GitHub Actions CI/CD (`.github/workflows/cd.yml`, secrets `VPS_HOST/VPS_USER/VPS_SSH_KEY`).
- **External APIs (all optional, degrade gracefully):** Hunter.io (email finding), ProxyCurl (LinkedIn data), Exa (neural web search), Resend (transactional email), YouTube Data API (interview prep videos), Google OAuth (Gmail `gmail.send/gmail.readonly/drive.readonly`), AgentQL, Firecrawl, RapidAPI/JSearch, Adzuna, Tavily/Brave/SerpAPI/Bing/Google CSE, Searxng self-hosted (`searxng/` dir exists)
- **LLM Providers (BYOK):** Anthropic Claude Sonnet 4.6/Haiku 4.5 (+extended thinking), OpenAI GPT-4o/mini + `text-embedding-3-small`, Google Gemini 2.0 Flash/Pro + `embedding-001`, Ollama local + `nomic-embed-text`, NVIDIA NIM Llama 3.1 70B (falls back to nomic-embed-text)
- **Browser:** Playwright/Chromium via `browser-use` lib, inside backend container, `shm_size 256m`, `mem_limit 2500m`, separate context per user
- **Tools:** Docker Compose, `supabase` CLI, `locustfile.py` (load test), `bandit` (SAST), `pip-audit`+`npm audit` in CI, `ruff`+`black`+`eslint`, `Makefile` commands

---

## 3. PROJECT STRUCTURE

### Top-level (`D:\CareerCraft AI` — 141 entries)
```
AGENTS.md, CLAUDE.md, README.md, PLAN.md, HOW_TO_RESTART.md, Makefile
.env.example, package.json (root, only headroom-ai), package-lock.json
docker-compose.yml (prod), docker-compose.dev.yml (dev hot-reload)
backend/, frontend/, worker/, supabase/migrations/, nginx/, docs/, scripts/
searxng/, applyos/ (dead fork, ignore), motionsites.ai-prompt-library/
assets/, output/, .browser_data/, node_modules/
*.log (backend-run.log, frontend-run.log, worker-run.log, *.err.log)
*.txt status files (AUTHENTICATION_*, CLERK_*, SECURITY_FIX_*, etc.)
*.png screenshots, test_*.py/sh, locustfile.py
.github/, .vscode/, .agents/, .claude/, .codex/, etc.
```

### Backend (`backend/app/`)
```
app/
  main.py — FastAPI factory (see §8). Routers at /api/v1 + /internal + /llm-gateway + /health
  agents/
    state.py — AgentState TypedDict (user_id/run_id required, rest optional, messages: list[Any] BaseMessage)
    orchestrator.py — supervisor StateGraph, TASK_ROUTES 14 mappings, _make_node_runner, build_graph() singleton
    harness.py — AgentHarness class + get_harness() singleton, 9-step run(), _select_strategy, reflect()
    base_agent.py — BaseAgent ABC (db, redis, set_run_id, abstract run(), _get_llm, _hitl_checkpoint)
    strategies.py, thinking.py (ThinkingWrapper/extended thinking), semantic_memory.py
    memory/ (SemanticMemoryBridge, routes)
    resume_agent.py, job_search.py, cover_letter_agent.py, linkedin_agent.py,
    linkedin_outreach_agent.py, email_agent.py, email_monitor_agent.py,
    followup_agent.py, interview_coach_agent.py, interview_prep_agent.py,
    company_research_agent.py, salary_agent.py, nl_search_agent.py,
    auto_apply_pipeline.py
    *_v2.py (9 untracked new versions: job_search_agent_v2, cover_letter_agent_v2, etc.)
  api/
    internal.py — worker-only (X-Internal-Secret, blocked at Nginx): run-job-search, run-followup, daily-search, check-status
    v1/
      deps.py — get_current_user (verify_auth_jwt, auto-provision User by supabase_uid), get_db
      run_utils.py — apply_harness_result()
      agents.py — POST /run {task_type,context} (VALID_TASKS 13), GET /{id}/stream (SSE 300s), POST /{id}/approve, GET /runs
      resume.py — POST /optimize (direct node call, no orchestrator) + GET /download/{id}
      jobs.py — POST /search (BullMQ enqueue), POST /search/natural (via Harness 120s), POST /applications/{id}/prepare-apply (browser max_steps 25)
      cover_letter.py, company.py, salary.py, interview.py, linkedin.py, email.py (all via Harness + wait_for timeout)
      rag.py — POST /upload (PDF/DOCX/TXT → chunk 500/50 → embeddings → pgvector {user_id}_{doc_type}), retrieval
      users.py, leads.py, interview_prep.py
  core/
    config.py — Settings (BaseSettings, see §8 full code), singleton settings=Settings()
    database.py — async SQLAlchemy engine
    supabase_auth.py — verify_token() HS256 audience=authenticated
    security.py — AES-256-GCM encrypt/decrypt (PBKDF2, unique salt per key)
    model_router.py — canonical get_llm(user_id,db,task_type), _build_llm, TokenTrackingCallback, CachingLLM (Redis 1h, skips email/auto_apply/etc), check_budget (429)
    llm_gateway.py — APIRouter /llm-gateway, proxy_llm_request, get_gateway_llm (key-free ChatOpenAI via session token)
    event_bus.py — Redis pub/sub emit/publish/stream_events for SSE
    rate_limit.py — slowapi, agent_runs_repository.py, redis_client.py, sync_db.py
  services/ (31 files)
    rag_service.py (ingest/retrieve), pdf_service.py (ReportLab), ats_service.py (keyword scoring),
    auto_apply_service.py, browser_control_service.py, browser_logger.py, company_careers_service.py,
    drive_service.py, email_finder_service.py, exa_service.py, form_filler_service.py,
    gmail_service.py (Gmail MCP), google_oauth_service.py, hunter_service.py,
    indian_platforms_service.py, job_platforms_service.py, linkedin_outreach_service.py,
    llm_gateway.py (get_llm decrypt BYOK → ChatAnthropic/OpenAI/Google/Ollama/NIM),
    llm_proxy_service.py, naukri_service.py, persona_service.py, proxycurl_service.py,
    queue_service.py (BullMQ enqueue), resend_service.py, search_presets.py,
    sse_service.py, storage_service.py, token_budget_service.py, youtube_service.py
  models/ — users, model_settings, documents, applications, leads, agent_runs, user_preferences, cover_letter_versions, interview_sessions, salary_reports, company_intel, resume_personas, linkedin_outreach_queue, ats_scores
  tools/ — ats_service.py, pdf_service.py, form_filler.py, platform_detector.py (untracked, new)
tests/
  unit/ (40 tests mocked fast CI per README; CLAUDE.md claims 285 across 34 files — DRIFT, verify with pytest)
  security/ (6 tests auth+validation)
  integration/ (opt-in INTEGRATION=1)
  e2e/ (untracked new)
```

**How agents connect to API (3 patterns):**
- A) Generic async: `POST /agents/run` → insert `AgentRun(running)` → `asyncio.create_task(_run_agent_background)` → `orchestrator.invoke` in executor with `AGENT_TIMEOUTS {auto_apply:300, job_search/company_research:120, cover_letter/salary:90, resume:60, interview_coach:30, default:60}` → update DB → `emit(complete|checkpoint|error)`
- B) Specialized sync via Harness: `jobs/search/natural, cover_letter, company, salary, interview, linkedin, email` → `get_harness().run()` + `apply_harness_result()` with `wait_for(timeout)`; Resume/Jobs-search direct node or BullMQ enqueue
- C) Internal worker: `POST /internal/*` with `X-Internal-Secret` → direct node calls, persists `JobApplication(saved)`, BullMQ cron

### Frontend (`frontend/src/`)
```
app/
  layout.tsx (Inter/DM_Sans/Instrument_Serif/Playfair_Display, Providers), globals.css (light --primary 146 60% 26% / .dark 258 80% 60%, liquid-glass utilities), error.tsx, not-found.tsx
  middleware.ts → lib/supabase/middleware.updateSession
  (marketing)/ layout (ThemeProvider light) + page, pricing, about, contact, docs, privacy, terms, status
  (auth)/ login/page, register/page (ui/sign-in.tsx, OAuth google/github/linkedin_oidc + password)
  (app)/ layout (ThemeProvider dark + OnboardingGuard > AppShell) + dashboard, jobs, resume, cover-letter, linkedin, linkedin/outreach, email, applications, interview, interview-prep, company, salary, leads, agents, onboarding, settings, settings/account, settings/models, settings/profile
  auth/callback/route.ts (exchangeCodeForSession, safeNextPath defaults /dashboard) + client/page, sso-callback/page
components/
  layout/: Providers (TanStack Query stale 5m/gc 10m, retry no on 401/403, GoogleOAuthSync, Toaster), AppShell (skips chrome on /onboarding, ConstellationBackground + ActiveRunStream + Sidebar + Topbar), AppSidebar, AppTopbar, AppImmersiveStage, ConstellationBackground, PageTransition
  auth/: OnboardingGuard (GET /users/me, redirects /onboarding, never auto-loops), UserMenu, GoogleOAuthSync
  agents/: AgentStatusCard, AgentStatusStream, ApprovalCard, ApprovalModal (HITL UI)
  ui/: button/card/badge/dialog/input/label/textarea/select/switch/tabs/scroll-area/sign-in, JobMatchCard, ResumeScoreCard, MetricCard, etc., LiquidGlassButton, VideoBackground, theme-switch
  marketing/: Navbar/Footer/HeroA/HeroB/FeaturesGrid/HowItWorks/PricingSection/FaqAccordion/MarqueeRow
  resume/: AtsScoreRing/KeywordCoverage/SuggestionsList/ResumeTemplates
  apps/: ApplicationKanban/ApplicationDrawer
  onboarding/: OnboardingStepper
  immersive/: CareerCommandScene/ImmersiveCanvas/MetricOrb/GlassSurface/VideoBackdrop/FilmGrain/BlurText/CommandHeader
  theme/: ThemeProvider/Toggle/theme-script, icons/BrandIcons
lib/
  api.ts (axios baseURL NEXT_PUBLIC_API_URL ?? localhost:8000/api/v1, Bearer injection via getSupabaseAuthToken, no auto-redirect, deduplicatedGet)
  sse.ts (useAgentStream: native fetch .../agents/{id}/stream, manual event:/data: parse, dispatches to Zustand, retry 2^n x3)
  auth.ts (server currentUser/auth), supabase.ts/client.ts/server.ts/middleware.ts, supabase-token.ts, google-oauth.ts (GMAIL_SCOPES, connectGoogleForGmail), sanitize.ts (DOMPurify allowlist p/br/strong/em/ul/ol/li/h1-4/code/pre/blockquote/a/span + href/class), utils.ts, motion-variants.ts
store/
  agentStore.ts (canonical: runs:Record<runId,AgentRun>, activeRunId persisted cc_active_run_id, initRun/addEvent/setCheckpoint/setComplete/setError, browser_frame → lastFrame only)
  agentSlice.ts (legacy duplicate), userSlice.ts (models list)
```

### Worker (`worker/src/processors/`)
`job-search.processor.ts`, `followup.processor.ts`, `daily-search.processor.ts`, `status-check.processor.ts` + `index.ts`

### Supabase (`supabase/migrations/` 32 files)
0001 users, 0002 model_settings, 0003 documents, 0004 applications, 0005 leads, 0006 agent_runs, 0007 pgvector HNSW, 0008 RLS, 0009 Clerk→Supabase, 0010 user_preferences, 0011 cover_letter_versions, 0012 interview_sessions, 0013 salary_reports, 0014 company_intel, 0015 resume_personas, 0016 linkedin_outreach_queue, 0017 ats_scores, 0018 RLS fix supabase_uid, 0019 linkedin credentials+auto, 0020 dashboard drift, 0021 google oauth tokens, 0022 job_application location, 0023 secure post-RLS, 0024 RLS with check, 0025 hnsw embeddings, 0026 feature+memory tables, 0027 signup metadata, 0028 clerk third-party RLS, 0029 years_experience check, 0030 enable RLS public, 0031 prefer_live_browser, 0032 rls+hnsw fixes

### Docs (`docs/`)
`API.md, ARCHITECTURE.md, BACKEND_AUTH_IMPLEMENTATION.md, BROWSER_EXTENSION_PROPOSAL.md, BROWSER_SCALING_ARCHITECTURE.md, CONFIGURATION.md, CONTRIBUTING.md, DATABASE.md, DEPLOYMENT.md, DEVELOPMENT.md, JOB_SEARCH_ANALYSIS.md, JOB_SEARCH_FIX.md, SECURITY.md, AGENTS_TROUBLESHOOTING.md, agent-system-technical-spec.md, audit-rebuild-plan.md` + `superpowers/` phase specs

### Key functions/classes/connections
- `AgentState` (state.py): `{user_id*, run_id*, task/task_type, status, context, messages: list[Any] BaseMessage, pending_action, result, error, tokens_used}`
- `orchestrator.TASK_ROUTES`: `resume_optimize→resume, job_search→job_search, cover_letter→cover_letter, linkedin_optimize→linkedin, email→email, interview_coach/evaluate_answer→interview_coach, interview_prep→interview_prep, company_research→company_research, salary_intelligence→salary, nl_job_search→nl_search, linkedin_outreach→linkedin_outreach, email_monitor→email_monitor, auto_apply→auto_apply`
- `AgentHarness.run(user_id,task_type,context,user_settings,run_id)` 9 steps → `{run_id,status,result,pending_action,error,strategy_used,duration_ms}`
- `BaseAgent._hitl_checkpoint()` → `redis.setex agent:{run_id}:pending + emitter.checkpoint + awaiting_approval`
- `get_llm(user_id,db)` / `model_router.get_llm(user_id,db,task_type)` — never hardcode model
- `verify_token()` HS256 audience `authenticated`; `get_current_user` auto-provisions User
- SSE events: `thinking {step,message}, tool_call {tool,input}, tool_result {tool,output}, checkpoint {action_type,details}, complete {result}, error {message}`

---

## 4. CURRENT STATE

### Already built & working
- All 7 phases per AGENTS.md/CLAUDE.md: P1 Foundation (25 unit), P2 RAG (+5), P3 Resume+LinkedIn (+7), P4 JobSearch+BullMQ (+3), P5 Email+FollowUp (+5), P6 Orchestrator+Frontend (+7), P7 Hardening (+6 security) = 46 tests (README). CLAUDE.md claims 285 across 34 files — discrepancy, verify via `pytest`.
- Auth migration Clerk→Supabase code-complete (commit `ad90e28 feat(frontend): migrate auth Clerk->Supabase`, `CLERK_REMOVAL_COMPLETE.md 2026-05-31`, no Clerk in package.json/requirements). Middleware, login/register, callback, OnboardingGuard, UserMenu, GoogleOAuthSync all implemented.
- Frontend dev server renders all main routes 200 (`/dashboard,/jobs,/applications,/agents,/email,/settings`, etc. per `frontend-run.log`).
- Backend boots, DB queries succeed (`users, user_model_settings, agent_runs` selects + ROLLBACK normal), agent polling 200.
- Worker boots, BullMQ listener alive, daily/status schedulers scheduled.
- Security fix: `/users/me/job-search-profile` server-side (`SECURITY_FIX_SUMMARY.md`). AES-256-GCM, RLS, rate limiting, Nginx blocks `/internal/*`, browser isolation, bandit, CVE patches claimed.
- Docs comprehensive: README (567 lines), ARCHITECTURE, API, DATABASE, DEPLOYMENT, DEVELOPMENT, SECURITY, CONFIGURATION.

### Partially done / dirty
- **Git dirty huge:** ~75 modified + ~70 untracked, nothing staged. Modified includes `.env.example, README, backend/app/agents/{harness,orchestrator,state,strategies,resume_agent,job_search,nl_search}, backend/app/api/{internal,v1/agents,jobs,rag}, backend/app/core/{config,database,event_bus,model_router,security,supabase_auth,sync_db}, backend/app/models/*, backend/app/services/{auto_apply,browser_control,form_filler,gmail,indian_platforms,job_platforms,queue}, constraints/requirements/pyproject, docker-compose*, frontend (agents/dashboard/jobs/resume/settings, components/agents, lib, store), nginx template, worker index/daily-search`. Untracked includes `*_v2.py` (9 files), `agent_runs_repository, redis_client, browser_logger, company_careers_service, llm_gateway, naukri_service, search_presets, sse_service`, `app/tools/`, new tests (~15), `docs/*`, migrations 0031/0032, `searxng/`, `applyos/`, restart scripts.
- `frontend/.../agents/page.tsx` has `// BUG 6/7/12/19` comments — annotations of already-applied fixes, left in code.
- `applyos/` fork has TODOs (dead code, ignore).
- Post-launch checklist unchecked (HNSW after first ingest, APP_ENV=production, Supabase Auth providers, Gmail scopes, Redis persist, pool alerts, BullBoard, Hunter/ProxyCurl/Exa keys).

### NOT started yet
- Production deploy (VPS setup, certbot, `docker compose up -d`, migrations push, GH secrets) — guide exists, not executed here.
- HNSW prod index run after first RAG ingestion.
- BullBoard queue visibility.
- Commit/push of current dirty tree + rebase onto `origin/main|master` (see §5).
- Fix Redis auth/eviction (see §5).
- Update stale docs (`HOW_TO_RESTART.md` Linux paths, `PLEASE_PROVIDE_INFO.md` Clerk refs).

---

## 5. PROBLEMS

### Current bugs — exact messages
1. **CRITICAL `backend-run.err.log` repeating:**
   ```
   Dev mode: Redis unavailable (Authentication required.) - running job-search inline
   redis.exceptions.AuthenticationError: Authentication required.
     File .../redis/asyncio/client.py subscribe -> event_bus.py:61 stream_events
   Unhandled exception on GET /api/v1/agents/.../stream: Authentication required.
   UserWarning: Duplicate Operation ID proxy_llm_request_llm_gateway_v1__path__post (llm_gateway.py)
   ```
   Cause: local Redis has password / `REDIS_PASSWORD` mismatch with backend `.env`. SSE stream crashes at `event_bus.py:61`. Job-search falls back to inline.

2. **`worker-run.err.log` BROKEN:**
   ```
   IMPORTANT! Eviction policy is allkeys-lru. It should be "noeviction" x5
   [worker] job repeat:status-check-scheduler:... failed: Status check failed for user all:
   ```
   Cause: local Redis not using `docker-compose.dev.yml` config (`--maxmemory-policy noeviction --requirepass`). Empty error = backend call failing. BullMQ job-loss risk.

3. **`frontend-dev.err.log` stale (ignore but note):**
   `Router action dispatched before initialization`, `Clerk loaded with development keys` — pre-migration log. Current code has no Clerk.

4. **`frontend-run.err.log` cosmetic only:**
   `Encountered a script tag while rendering React component... use template tag` — non-fatal.

5. **Git divergence:**
   - Branch `* master` local, also `+ worktree-swarm-fix` local. Remotes `origin/main, origin/master (HEAD->origin/main)`.
   - Log `--oneline -20` (only 9 exist):
     ```
     ad90e28 (HEAD->master) feat(frontend): migrate auth Clerk->Supabase
     d4ba26a feat(db): enable RLS on public tables, lock down trigger RPCs
     1f7dbf3 fix(backend): 24-bug audit pass — security, infra, agents
     bbfa494 chore: remove dead PinchTab code (superseded by browser-use)
     9c5aee chore: ignore root .txt/.png + test output, untrack clutter
     f106703 (tag: backup/bolt-dashboard-stats) Save full working state
     0e26aee perf(api): aggregate dashboard stats
     9627bfa (tag: backup/palette-profile-chip-a11y) fix(profile): chip a11y
     a78fbc Initial commit
     ```
   - `origin/master...HEAD: 98 9` (98 remote not in local, 9 local not remote). `origin/main...HEAD: 3 9` diverged both ways. Do NOT `push --force` without fetch+diff.

6. **Docs drift:**
   - `HOW_TO_RESTART.md` references `/mnt/d/...`, `pkill next dev`, `lsof`, Clerk OAuth — wrong for win32 PowerShell + Supabase.
   - `PLEASE_PROVIDE_INFO.md` asks about `/test-clerk`, port 3002.
   - `AUTHENTICATION_MIGRATION_TODO.md` describes Phase 1-4 Clerk→Supabase but migration already done — outdated.
   - `README` says Next.js 14 but `package.json` is Next 16.2.6. Test count 46 vs 285 conflict.

### Tried that did NOT work / confusing
- Local Redis without password vs backend expecting password → auth fails; inline fallback masks it but SSE still crashes. Fix is env alignment, not code change.
- Worker status-check with empty error — backend call failing, not worker logic; need backend logs + INTERNAL_SECRET check.
- `Duplicate Operation ID` warning — two `llm_gateway.py` (core vs services) both define proxy route; harmless but confusing; needs dedup.
- `TODO/FIXME` grep finds no open items in `backend/app/*` except dead `applyos/` fork — real remaining work is env/git, not code TODOs.

---

## 6. IMPORTANT DECISIONS & RULES

- **HITL mandatory:** never send email or submit application without explicit UI approval. Only send path is `/email/approve/{id}`; only submit via `/agents/{id}/approve` after `checkpoint`. 2 checkpoints for auto-apply, cannot be bypassed.
- **API keys AES-256-GCM (PBKDF2, unique salt per key), decrypted only at request time.** Never store plaintext in `user_model_settings.api_key_enc`.
- **Always log to `agent_runs`** (status, input, output, tokens_used, duration_ms).
- **Never hardcode model names.** Always use `llm_gateway.py` / `model_router.py` (`get_llm`). Extended thinking only for `claude-3-7-sonnet/claude-sonnet-4/opus-4`, budget `AGENT_THINKING_BUDGET_TOKENS=8000`.
- **Browser Use human-like delays** (LinkedIn/Naukri ToS risk): navigate 1500-3500ms, fill 300-800ms, click 200-600ms, extract 500-1500ms (config.py). Separate browser context per user. `shm_size 256m`, mem cap.
- **pgvector HNSW required for prod scale.** Collections `{user_id}_{doc_type}` (resume/achievements/certifications/portfolio/notes), chunk 500/50, top_k 5.
- **Auth:** Supabase JWT HS256 audience `authenticated`, verified every protected route. Frontend `@supabase/ssr` cookies, middleware refreshes. Backend `SUPABASE_JWT_SECRET` local verify. RLS — users only own data. `on_auth_user_created` trigger auto-provisions `public.users` by `supabase_uid`.
- **CORS:** reject `*`, exact origins only. Auto-adds `localhost:3000` when not prod.
- **No auto-redirect on 401** in `api.ts` or guards — show error + “Log in again” button to avoid dashboard↔login loop. `deduplicatedGet` for concurrent GETs. Sanitize LLM output via DOMPurify allowlist.
- **Concurrency:** max 2 concurrent runs per user (BullMQ + `AGENT_MAX_CONCURRENT_PER_USER`). Timeouts: auto_apply 300s, job_search/company 120s, cover_letter/salary 90s, resume 60s, interview_coach 30s/turn, default 60s. Token budgets: cover_letter/salary 6000, company 5000, resume 4000, interview 2000/turn, others 3000 (configurable `user_model_settings.token_budget`).
- **SSE events only:** `thinking/tool_call/tool_result/checkpoint/complete/error`. `/internal/*` blocked at Nginx.
- **Coding style:** `ruff + black` (backend, py312), `eslint` (frontend, `no-explicit-any:off`). No `*` CORS, no `print` secrets, `REDIS_URL_SAFE` redacts password.
- **What user does NOT want:** no bypassing HITL, no plaintext keys, no force-push without review, no `*` CORS, no auto-redirect loops, no hardcoded models, no lowering browser delays (detection risk), no committing secrets (`.env` never committed, only `.env.example`), no new markdown files unless requested, no file ops via bash (use Read/Edit/Write tools).

---

## 7. SETUP & RUN INSTRUCTIONS

### Prerequisites
- Docker + Docker Compose, Supabase project (free tier ok), at least one AI provider key (Anthropic/OpenAI/Google or local Ollama), Node 24, Python 3.12

### 1. Clone + configure
```bash
git clone https://github.com/blu59204/CareerCraftsAI.git
cd CareerCraftsAI
cp .env.example .env
```
Fill `.env` (REQUIRED):
```bash
APP_SECRET_KEY=<openssl rand -hex 32>
DATABASE_URL=postgresql+asyncpg://postgres:[password]@db.[project].supabase.co:5432/postgres
SUPABASE_URL=https://[project].supabase.co
SUPABASE_SERVICE_KEY=<service_role, NEVER frontend>
SUPABASE_JWT_SECRET=<Settings → API → JWT Secret>
NEXT_PUBLIC_SUPABASE_URL=https://[project].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=changeme
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
INTERNAL_SECRET=<random>
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000
BACKEND_INTERNAL_URL=http://backend:8000
# Optional: HUNTER_API_KEY, PROXYCURL_API_KEY, EXA_API_KEY, RESEND_API_KEY, YOUTUBE_API_KEY,
# GOOGLE_OAUTH_CLIENT_ID/SECRET, AGENTQL/FIRECRAWL/RAPIDAPI/ADZUNA/TAVILY/BRAVE/SERPAPI/BING/GOOGLE_CSE, SEARXNG_URL
```
Frontend `.env.local` (actual current values include `NEXT_PUBLIC_SUPABASE_URL=https://bxngbveaiqxryefbtlst.supabase.co`, `NEXT_PUBLIC_API_URL=/api/v1` prod rewrite to avoid Docker DNS leak, `NEXT_PUBLIC_BACKEND_URL=http://backend:8000`).

### 2. Migrations
```bash
supabase db push --db-url "$DATABASE_URL"
# 32 files in supabase/migrations/, includes RLS + HNSW
```

### 3. Run
```bash
make dev   # docker compose -f docker-compose.dev.yml up --build (hot reload)
# Frontend http://localhost:3000, Backend docs http://localhost:8000/docs, Redis localhost:6379
```
Backend only:
```bash
cd backend
pip install -r requirements.txt -c constraints.txt
uvicorn app.main:app --reload --port 8000
```
Frontend only: `cd frontend; npm install; npm run dev`
Worker only: `cd worker; npm install; npm run build; npm run dev`
Prod: `docker compose up -d; docker compose ps; curl https://yourdomain.com/health`

### 4. Test/lint
```bash
make test  # cd backend && pytest tests/unit -v (README: 46 tests)
make lint  # ruff check + black --check + eslint
make format; make build; make clean  # clean = down -v
cd backend; pytest tests/unit -v; pytest tests/security -v; pytest tests/unit tests/security -v
pytest -k "test_name" -v; bandit -r app/ -f txt; ruff check . && black --check .
cd frontend; npm run build; npm run lint; npm run type-check  # tsc --noEmit; npm run test # jest
cd worker; npm run build
locust --host=http://localhost:8000 --users=20 --spawn-rate=4 --run-time=30s --headless  # needs LOAD_TEST_TOKEN
```
Windows note: run pytest via `.venv/Scripts/python -m pytest`, not system python. Current `HOW_TO_RESTART.md` Linux commands (`pkill`, `lsof`, `/mnt/d`) do NOT apply on win32 — use Task Manager / `Get-Process` / `Remove-Item .next`.

### 5. App bootstrap
Settings → AI Models → add key. Resume → Upload PDF/DOCX (seeds RAG). Supabase Auth providers + redirect URLs + Gmail scopes `gmail.send,gmail.readonly,drive.readonly`.

---

## 8. CODE

> Full repo is ~1000+ files — cannot paste all here. Below are the FULL current contents of the most critical files (verified by Read). For all other files use the exact paths + key symbols in §3. New assistant should Read those paths directly.

### 8.1 `backend/app/agents/state.py` (FULL, 45 lines)
```python
from __future__ import annotations

from typing import Any, Literal, TypedDict


class AgentEvent(TypedDict):
    event_type: Literal["thinking", "tool_call", "tool_result", "checkpoint", "complete", "error"]
    payload: dict
    timestamp: str


class CheckpointPayload(TypedDict):
    action_type: str
    details: dict


class _AgentStateRequired(TypedDict):
    """Fields every node may read — KeyError-safe only when these are always present."""
    user_id: str
    run_id: str


class AgentState(_AgentStateRequired, total=False):
    """Shared state passed between LangGraph nodes.

    Required fields (user_id, run_id) are declared in _AgentStateRequired so
    that TypedDict enforcement makes them non-optional.  All other fields are
    optional (total=False) to allow partial updates at each node.

    messages holds langchain BaseMessage objects (AIMessage, HumanMessage, etc.)
    not plain dicts — the list[dict] annotation in the original schema was wrong
    and caused silent type mismatches at serialisation time.
    """
    task: str
    task_type: str
    status: str
    context: dict
    # Holds langchain BaseMessage instances (AIMessage, HumanMessage, etc.)
    messages: list[Any]
    pending_action: dict | None
    result: dict | None
    error: str | None
    # Total tokens consumed by this run — written by ResumeAgent and any agent
    # that tracks token usage; read by agent_runs_repository for billing records.
    tokens_used: int
```

### 8.2 `backend/app/core/config.py` (FULL, 135 lines)
```python
from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — single source of truth for all env vars.

    Required vars cause a clear Pydantic ValidationError at startup if missing.
    Optional vars have safe defaults so the app starts without them.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Required — app exits with clear error if any are missing ────────
    APP_SECRET_KEY: str
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_JWT_SECRET: str
    NEXT_PUBLIC_SUPABASE_URL: str = ""
    NEXT_PUBLIC_SUPABASE_ANON_KEY: str = ""
    REDIS_URL: str

    # ── App environment ────────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    FRONTEND_URL: str = "http://localhost:3000"

    # ── CORS ───────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    # ── Next.js public URLs ────────────────────────────────────────────
    NEXT_PUBLIC_APP_URL: str = "http://localhost:3000"
    NEXT_PUBLIC_API_URL: str = "http://localhost:8000"

    # ── Redis ──────────────────────────────────────────────────────────
    REDIS_PASSWORD: str | None = None

    # ── Internal / gateway ─────────────────────────────────────────────
    INTERNAL_SECRET: str = ""
    BACKEND_INTERNAL_URL: str = "http://backend:8000"
    LLM_GATEWAY_URL: str = "http://localhost:8000/llm-gateway/v1"

    # ── Browser Use ────────────────────────────────────────────────────
    BROWSER_USE_OLLAMA_MODEL: str = "llama3.2"
    BROWSER_USE_OLLAMA_URL: str = ""
    BROWSER_USE_MAX_CONCURRENT_SESSIONS: int = 4
    BROWSER_USE_SESSION_MEM_LIMIT_MB: int = 500
    BROWSER_DEBUG_SCREENSHOTS: bool = False
    BROWSER_DEBUG_DIR: str = "/tmp/browser_debug"
    BROWSER_DELAY_NAVIGATE_MIN_MS: int = 1500
    BROWSER_DELAY_NAVIGATE_MAX_MS: int = 3500
    BROWSER_DELAY_FILL_MIN_MS: int = 300
    BROWSER_DELAY_FILL_MAX_MS: int = 800
    BROWSER_DELAY_CLICK_MIN_MS: int = 200
    BROWSER_DELAY_CLICK_MAX_MS: int = 600
    BROWSER_DELAY_EXTRACT_MIN_MS: int = 500
    BROWSER_DELAY_EXTRACT_MAX_MS: int = 1500

    # ── External API keys (all optional) ───────────────────────────────
    HUNTER_API_KEY: str = ""
    PROXYCURL_API_KEY: str = ""
    EXA_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    YOUTUBE_API_KEY: str = ""
    AGENTQL_API_KEY: str | None = None
    FIRECRAWL_API_KEY: str | None = None
    SEARXNG_URL: str | None = None
    RAPIDAPI_KEY: str | None = None
    ADZUNA_APP_ID: str | None = None
    ADZUNA_APP_KEY: str | None = None
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: str | None = None

    # ── Search providers ───────────────────────────────────────────────
    TAVILY_API_KEY: str | None = None
    BRAVE_API_KEY: str | None = None
    SERPAPI_API_KEY: str | None = None
    BING_SEARCH_API_KEY: str | None = None
    GOOGLE_CSE_API_KEY: str | None = None
    GOOGLE_CSE_ID: str | None = None
    DUCKDUCKGO_ENABLED: bool = True
    MOJEEK_ENABLED: bool = True

    # ── Agent configuration ────────────────────────────────────────────
    AGENT_DEFAULT_TIMEOUT_S: int = 60
    AGENT_MAX_CONCURRENT_PER_USER: int = 2
    AGENT_THINKING_BUDGET_TOKENS: int = 8000

    # ── RAG configuration ──────────────────────────────────────────────
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 5

    # ── Rate limiting ──────────────────────────────────────────────────
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_AGENT_RUN: str = "10/minute"
    RATE_LIMIT_UPLOAD: str = "5/minute"
    RATE_LIMIT_STR: str = "100/minute"

    # ── Supabase Storage ───────────────────────────────────────────────
    SUPABASE_STORAGE_BUCKET: str = "documents"

    @model_validator(mode="after")
    def _inject_redis_password(self) -> "Settings":
        if (
            self.REDIS_PASSWORD
            and self.REDIS_URL.startswith("redis://")
            and "@" not in self.REDIS_URL.split("redis://", 1)[1].split("/", 1)[0]
        ):
            self.REDIS_URL = self.REDIS_URL.replace(
                "redis://", f"redis://:{self.REDIS_PASSWORD}@", 1
            )
        return self

    @property
    def REDIS_URL_SAFE(self) -> str:
        import re
        url = self.REDIS_URL
        return re.sub(r"://.*@", "://***@", url)


settings = Settings()
```

### 8.3 `frontend/src/lib/api.ts` (FULL, 64 lines)
```typescript
import axios from "axios";
import { getSupabaseAuthToken } from "@/lib/supabase-token";

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// Deduplicate concurrent identical GET requests
const pendingRequests = new Map<string, Promise<unknown>>();

apiClient.interceptors.request.use(async (config) => {
  if (typeof window !== "undefined") {
    try {
      const token = await getSupabaseAuthToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch {
      // not authenticated — request will get 401, guard handles redirect
    }
  }
  return config;
});

// Response interceptor — log the failure and reject. We do NOT auto-redirect or
// loop on 401 here; the auth guard surfaces a single error page and lets the user
// choose to log in again. This avoids the dashboard⇄login redirect loop.
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (typeof window !== "undefined" && error?.response) {
      const { config, response } = error;
      console.error(
        `API ${config?.method?.toUpperCase?.() ?? "?"} ${config?.url ?? "?"} -> ${response.status}`,
        response.data?.detail ?? response.data,
      );
    }
    return Promise.reject(error);
  }
);

export async function deduplicatedGet<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const key = `${url}?${JSON.stringify(params ?? {})}`;
  const existing = pendingRequests.get(key);
  if (existing) return existing as Promise<T>;
  const promise = apiClient.get(url, { params }).then((r) => {
    pendingRequests.delete(key);
    return r.data as T;
  }).catch((err) => {
    pendingRequests.delete(key);
    throw err;
  });
  pendingRequests.set(key, promise);
  return promise;
}
```

### 8.4 `frontend/package.json` (FULL)
```json
{
  "name": "jobagent-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "@microsoft/fetch-event-source": "^2.0.1",
    "@radix-ui/react-accordion": "^1.2.12",
    "@radix-ui/react-avatar": "^1.1.11",
    "@radix-ui/react-dialog": "^1.1.15",
    "@radix-ui/react-label": "^2.1.8",
    "@radix-ui/react-scroll-area": "^1.2.10",
    "@radix-ui/react-select": "^2.2.6",
    "@radix-ui/react-separator": "^1.1.8",
    "@radix-ui/react-slot": "^1.2.4",
    "@radix-ui/react-switch": "^1.2.6",
    "@radix-ui/react-tabs": "^1.1.13",
    "@react-three/drei": "^10.7.7",
    "@react-three/fiber": "^9.6.1",
    "@supabase/auth-helpers-nextjs": "^0.15.0",
    "@supabase/ssr": "^0.10.3",
    "@supabase/supabase-js": "^2.106.2",
    "@tanstack/react-query": "^5.100.14",
    "@tanstack/react-query-devtools": "^5.100.14",
    "axios": "^1.16.1",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "dompurify": "^3.4.7",
    "lucide-react": "^1.17.0",
    "motion": "^12.40.0",
    "next": "^16.2.6",
    "next-themes": "^0.4.6",
    "react": "^19.2.6",
    "react-dom": "^19.2.6",
    "sonner": "^2.0.7",
    "tailwind-merge": "^3.6.0",
    "three": "^0.181.2",
    "zustand": "^5.0.13"
  },
  "devDependencies": {
    "@types/dompurify": "^3.0.5",
    "@types/node": "^25.9.1",
    "@types/react": "^19.2.15",
    "@types/react-dom": "^19.2.3",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.39.4",
    "eslint-config-next": "^16.2.6",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17",
    "typescript": "^6.0.3"
  }
}
```

### 8.5 `worker/package.json` (FULL)
```json
{
  "name": "jobagent-worker",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "node --env-file=.env -r ts-node/register src/index.ts"
  },
  "dependencies": {
    "axios": "^1.16.1",
    "bullmq": "^5.77.6",
    "ioredis": "^5.11.0"
  },
  "devDependencies": {
    "@types/node": "^22.10.2",
    "ts-node": "^10.9.2",
    "typescript": "^6.0.3"
  }
}
```

### 8.6 `Makefile` (FULL)
```make
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

### 8.7 `.env.example` (FULL — 81 lines, see file)
Key required: `APP_SECRET_KEY, DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_JWT_SECRET, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, REDIS_URL, REDIS_PASSWORD, INTERNAL_SECRET`. Optional: Resend, YouTube, Google OAuth, Hunter/ProxyCurl/Exa/AgentQL/Firecrawl/RapidAPI/Adzuna, Tavily/Brave/SerpAPI/Bing/Google CSE, Searxng, LLM gateway, agent timeouts/budgets, RAG chunk/top_k, rate limits. Full text in `D:\CareerCraft AI\.env.example`.

### 8.8 `docker-compose.yml` + `docker-compose.dev.yml` (FULL — see files)
Prod: frontend:3000 (waits backend healthy), backend:8000 (mem 2500m, shm 256m, volume browser_debug, health /health), worker (waits redis+backend), redis:8-alpine (appendonly, 512mb, noeviction, requirepass), nginx:80/443 (DOMAIN envsubst, blocks /internal). Dev: same but hot-reload volumes + `npm run dev` / `uvicorn --reload` / `nodemon ts-node`, single `.env` file.

### 8.9 Other important files — READ THESE DIRECTLY (too long to paste)
- `backend/app/main.py` (235 lines) — FastAPI factory, `_REQUIRED_VARS`, `_check_env_vars` sys.exit(1), `_build_cors_origins` rejects `*`, `_request_id_middleware`, `_jwt_middleware` (skips /health/docs/redoc/openapi/internal + OPTIONS), `_lifespan` (DB/Redis/vector check), routers, `GET /health {status,version,db,redis,pgvector}`
- `backend/app/agents/orchestrator.py` — TASK_ROUTES table (§3), `_route_task`, `_make_node_runner` (emit + upsert_agent_run), `build_graph()` singleton
- `backend/app/agents/harness.py` — `AgentHarness.run()` 9 steps, `reflect()` 24h/20-episode guard
- `backend/app/agents/base_agent.py` — `BaseAgent`, `_hitl_checkpoint`
- `backend/app/core/security.py` — AES-256-GCM encrypt/decrypt
- `backend/app/core/supabase_auth.py` — `verify_token`
- `backend/app/core/model_router.py` + `backend/app/services/llm_gateway.py` — BYOK routing
- `backend/app/core/event_bus.py:61` — SSE `stream_events` (crash site)
- `backend/app/api/v1/agents.py` — run/stream/approve
- `backend/app/api/internal.py` — worker endpoints
- `frontend/src/lib/sse.ts`, `store/agentStore.ts`, `app/(app)/agents/page.tsx` (has BUG comments), `components/agents/ApprovalModal.tsx`, `middleware.ts`, `app/auth/callback/route.ts`
- `backend/requirements.txt` + `constraints.txt` (exact pins §2)
- `supabase/migrations/0031_*.sql`, `0032_*.sql` (latest)
- `docs/API.md`, `ARCHITECTURE.md`, `DATABASE.md`, `DEPLOYMENT.md`, `SECURITY.md`

---

## 9. NEXT STEPS (priority order)

1. **Fix Redis auth mismatch (P0, blocks SSE + worker):** ensure local Redis password == `REDIS_PASSWORD` in `.env` and `REDIS_URL`. If using Docker dev stack, `docker compose -f docker-compose.dev.yml up redis` already sets `--requirepass ${REDIS_PASSWORD:-changeme} --maxmemory-policy noeviction`. If running Redis locally outside Docker, restart with those flags. Verify: `redis-cli -a $REDIS_PASSWORD ping` → `PONG`, then `GET /api/v1/agents/{id}/stream` no longer throws `Authentication required` at `event_bus.py:61`.
2. **Fix Redis eviction (P0):** `CONFIG SET maxmemory-policy noeviction` or restart with correct flags. Verify `CONFIG GET maxmemory-policy` → `noeviction`.
3. **Verify worker (P0):** check `INTERNAL_SECRET` matches backend/worker `.env`, then trigger `status-check` manually, confirm no `Status check failed for user all:` empty error.
4. **Dedup `Duplicate Operation ID` warning (P1):** rename one `proxy_llm_request` in `core/llm_gateway.py` vs `services/llm_gateway.py` or set distinct `operation_id`.
5. **Git hygiene (P1):** `git fetch origin; git status; git diff --stat; git diff origin/main...HEAD` — decide rebase vs merge. Stage in small commits (backend agents, frontend auth, migrations, docs separately). Do NOT force-push. Handle 75 modified + 70 untracked + `*_v2.py` files (decide keep vs merge into v1).
6. **Run tests to resolve count drift (P1):** `cd backend; .venv/Scripts/python -m pytest tests/unit tests/security -v` — confirm 46 vs 285. Run `ruff check + black --check`, `cd frontend; npm run lint; npm run type-check; npm run build`.
7. **Update stale docs (P2):** rewrite `HOW_TO_RESTART.md` for win32 PowerShell + Supabase (remove `/mnt/d`, `pkill`, `lsof`, Clerk), archive `AUTHENTICATION_MIGRATION_TODO.md`, fix `PLEASE_PROVIDE_INFO.md`, align README Next.js 14→16.2.6 if intentional.
8. **Post-launch checklist (P2):** run HNSW migration after first RAG ingest, set `APP_ENV=production`, configure Supabase Auth providers + redirect URLs + Gmail scopes, verify Redis persist volume, pool alerts, add BullBoard, set Hunter/ProxyCurl/Exa keys.
9. **Production deploy (when ready):** VPS Ubuntu 22.04 `/opt/careercraft`, `cp .env.example .env`, `certbot --nginx -d DOMAIN`, `sed s/${DOMAIN}/.../ nginx.conf`, `docker compose up -d`, `supabase db push`, GH secrets `VPS_HOST/VPS_USER/VPS_SSH_KEY`, push to `main` triggers `cd.yml`.
10. **What I was about to do next:** same as #1-3 — fix local Redis so SSE streaming + BullMQ worker pass, then commit cleanly. No new features until env is green.

---
**End of handoff. New assistant: start by reading `README.md`, `AGENTS.md`, `CLAUDE.md`, `.env.example`, `backend/app/main.py`, `backend/app/agents/state.py`, `orchestrator.py`, `frontend/src/lib/api.ts`, `Makefile`, and running `git status` + `git log --oneline -10` in `D:\CareerCraft AI`.**
