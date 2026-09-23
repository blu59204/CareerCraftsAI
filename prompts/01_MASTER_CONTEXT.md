# PROJECT CONTEXT — CareerCraft AI (paste at top of every prompt)

## What it is
Full-stack multi-agent job-search automation. 15 LangGraph agents under a supervisor (orchestrator).
BYOK: user brings own LLM key (Anthropic / OpenAI / Google / Ollama / NVIDIA NIM). Keys stored AES-256-GCM.
Every email send or job application submit REQUIRES human approval (HITL checkpoint via SSE + POST /approve).
Currently: NOTHING works end-to-end. We are making it work one slice at a time.

## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy async + asyncpg, LangGraph 0.2.76, langchain-core 0.3.86,
  langchain-anthropic 0.3.22, langchain-openai 0.3.35, langchain-google-genai 2.1.12, langchain-ollama 0.3.10,
  pgvector, Redis (event bus + cache + BullMQ), Playwright via browser-use 0.12.9, reportlab (PDF), python-jobspy.
  Pins live in backend/constraints.txt (wins over requirements.txt).
- Frontend: Next.js 16.2.6 (App Router), React 19, TypeScript 6 strict, Tailwind 3.4, Zustand 5, TanStack Query 5,
  @supabase/ssr, axios, Radix UI, motion. Path alias @/* -> src/*.
- Worker: Node 24, TypeScript, BullMQ 5, ioredis. Processors: job-search, followup, daily-search, status-check.
- DB/Auth: Supabase (Postgres 16 + pgvector + Auth + Storage). 32 migrations in supabase/migrations/. RLS on.
- Infra: Docker Compose (docker-compose.yml prod, docker-compose.dev.yml dev), Nginx, GitHub Actions.
- OS: Windows 11, PowerShell 5.1. Repo root: D:\CareerCraft AI (git branch master).

## Key paths
backend/app/main.py                    FastAPI factory, routers at /api/v1, /internal, /llm-gateway, /health
backend/app/core/config.py             Settings (pydantic BaseSettings). Single source of env vars.
backend/app/core/database.py           async engine + get_db
backend/app/core/supabase_auth.py      verify_token() HS256, audience "authenticated"
backend/app/core/security.py           AES-256-GCM encrypt/decrypt for API keys
backend/app/core/model_router.py       get_llm(user_id, db, task_type) — THE way to get an LLM. Never hardcode models.
backend/app/core/event_bus.py          Redis pub/sub: emit(run_id, event_type, payload), stream_events(run_id)
backend/app/core/llm_gateway.py        /llm-gateway proxy (DUPLICATE of services/llm_gateway.py — see rules)
backend/app/agents/state.py            AgentState TypedDict (user_id, run_id required)
backend/app/agents/orchestrator.py     supervisor StateGraph, TASK_ROUTES dict, build_graph()
backend/app/agents/harness.py          AgentHarness.run() wraps a node with strategy/reflection
backend/app/agents/base_agent.py       BaseAgent ABC: run(), _get_llm(), _hitl_checkpoint()
backend/app/agents/<name>_agent.py     one file per agent (also *_v2.py untracked duplicates)
backend/app/api/v1/agents.py           POST /run, GET /{id}/stream (SSE), POST /{id}/approve, GET /runs
backend/app/api/v1/*.py                resume, jobs, cover_letter, company, salary, interview, linkedin, email, rag, users
backend/app/api/internal.py            worker-only endpoints, header X-Internal-Secret
backend/app/services/*.py              rag_service, pdf_service, ats_service, gmail_service, queue_service, etc.
backend/app/models/*.py                SQLAlchemy models: users, model_settings, documents, applications, agent_runs...
frontend/src/lib/api.ts                axios client, Bearer from Supabase session, deduplicatedGet()
frontend/src/lib/sse.ts                useAgentStream(runId) → Zustand agentStore
frontend/src/store/agentStore.ts       canonical run store (agentSlice.ts is a legacy duplicate)
frontend/src/app/(app)/*               dashboard, jobs, resume, cover-letter, linkedin, email, applications, interview,
                                       interview-prep, company, salary, leads, agents, onboarding, settings/*
frontend/src/components/agents/*       AgentStatusStream, ApprovalModal (HITL UI)
worker/src/processors/*.ts             BullMQ processors
supabase/migrations/0001..0032         schema, RLS, HNSW

## Contracts that everything depends on
AgentState = { user_id*, run_id*, task_type, status, context: dict, messages: list[BaseMessage],
               pending_action: dict|None, result: dict|None, error: str|None, tokens_used: int }
SSE event types (ONLY these): thinking {step,message} | tool_call {tool,input} | tool_result {tool,output}
               | checkpoint {action_type,details} | complete {result} | error {message}
TASK_ROUTES keys: resume_optimize, job_search, cover_letter, linkedin_optimize, email, interview_coach,
               evaluate_answer, interview_prep, company_research, salary_intelligence, nl_job_search,
               linkedin_outreach, email_monitor, auto_apply
HITL: agent calls self._hitl_checkpoint(action_type, details) → sets redis agent:{run_id}:pending,
      emits checkpoint, returns status "awaiting_approval". POST /agents/{id}/approve resumes it.
Agent return shape: {"status": "complete"|"awaiting_approval"|"error", "result": {...}|None, "error": str|None}
Timeouts: auto_apply 300s, job_search/company_research 120s, cover_letter/salary 90s, resume 60s,
          interview_coach 30s/turn, default 60s.
Token budgets: cover_letter/salary 6000, company 5000, resume 4000, interview 2000/turn, others 3000.

## Known-broken right now
- Redis auth mismatch → SSE crashes at event_bus.py:61 "Authentication required"; worker sees eviction policy
  allkeys-lru instead of noeviction.
- Duplicate FastAPI operation id proxy_llm_request (core/llm_gateway.py vs services/llm_gateway.py)
- 9 untracked *_v2.py agents duplicating v1 agents; agentSlice.ts duplicates agentStore.ts
- Git: ~75 modified, ~70 untracked, local master diverged from origin/main and origin/master
- Test count claims conflict (46 vs 285)
- No feature works end-to-end in the UI.
