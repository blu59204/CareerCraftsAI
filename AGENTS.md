# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project

**JobAgent AI** — multi-agent job search automation platform. Users bring own API keys (BYOK). Agents handle resume tailoring, job search, auto-apply, LinkedIn optimization, and follow-up emails.

PRD: `CareerCraft AI.md` — authoritative source for product decisions.

---

## Architecture

4-layer stack:

```
Next.js 14 App Router (port 3000)
    ↓
FastAPI Python 3.12 (port 8000)
    ↓
LangGraph agent harness
    ↓
PostgreSQL/pgvector (Supabase) + Redis + PinchTab (port 9867)
```

**Agents** (all in LangGraph): Orchestrator (supervisor), JobSearch, Resume, LinkedIn, Email (Gmail MCP), FollowUp, RAG.

**Model router** — user supplies API key per provider: Anthropic, OpenAI, Google, Ollama, NVIDIA NIM. Active model stored in `user_model_settings`. All agent calls go through this router — never hardcode a model.

**RAG** — pgvector via LangChain PGVector class. Collections namespaced `{user_id}_{doc_type}` (e.g. `usr_abc123_resume`). chunk_size=500, overlap=50.

**Browser automation** — PinchTab MCP binary for job board interaction (LinkedIn, Naukri). Runs as separate Docker service.

**Queue** — BullMQ (Node.js worker) backed by Redis. Max concurrency per user = 2.

**Auth** — Supabase Auth. Methods: Google OAuth, LinkedIn (OIDC), GitHub, email/password, magic link. Google OAuth scopes include `gmail.send`, `gmail.readonly`, `drive.readonly` for Email Agent. Frontend uses `@supabase/ssr` for cookie-based sessions; middleware refreshes tokens. Backend verifies access tokens locally with `SUPABASE_JWT_SECRET` (HS256, audience=`authenticated`). Postgres trigger `on_auth_user_created` auto-provisions `public.users` rows on signup, keyed by `supabase_uid`.

---

## Tech Stack Quick Reference

| Concern | Choice |
|---|---|
| Frontend | Next.js 14 App Router + Tailwind + shadcn/ui + Zustand + TanStack Query v5 |
| Backend | FastAPI 0.111+ / Python 3.12 |
| Agents | LangGraph 0.2+ / LangChain 0.3+ |
| Primary LLM | Codex-sonnet-4-6 |
| DB | Supabase (PostgreSQL 16 + pgvector 0.7+) |
| Cache/Queue | Redis 7 + BullMQ 5 |
| PDF gen | ReportLab 4 |
| Doc parsing | PyMuPDF (PDF) + python-docx (DOCX) |
| Email delivery | Resend |
| Proxy | Nginx + Certbot |
| Containers | Docker Compose |

---

## Commands

### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev        # dev server :3000
npm run build
npm run lint
npm run test       # jest
npm run test -- --testPathPattern=<file>  # single test
```

### Backend (FastAPI)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest tests/unit tests/security -v   # all tests (46 total)
pytest tests/unit -v                  # unit tests only (40)
pytest tests/security -v              # security tests only (6)
pytest -k "test_name"                 # single test
```

### Docker (full stack)
```bash
docker compose up --build       # start all services
docker compose up frontend backend  # specific services
docker compose logs -f backend  # tail logs
```

### Security & Load Testing
```bash
# Bandit static analysis
cd backend && bandit -r app/ -f txt

# Locust load test (requires running server + LOAD_TEST_TOKEN env var)
locust --host=http://localhost:8000 --users=20 --spawn-rate=4 --run-time=30s --headless
```

### Database
```bash
# Supabase migrations (from /backend or /supabase dir)
supabase db push
supabase db reset   # WARNING: drops all data
```

---

## Key Constraints

- **Human-in-the-loop gate** required before any email send or job application submit — never automate past this without explicit user approval in UI.
- **API keys** encrypted AES-256 before DB storage — never store plaintext keys in `user_model_settings.api_key_enc`.
- **Agent actions** always logged to `agent_runs` table (status, input, output, tokens_used, duration_ms).
- LinkedIn/Naukri automation may violate ToS — PinchTab interactions must use human-like delays.
- pgvector collections require HNSW index for production scale.

---

## Page Routes

See PRD §3.1 for full route tree. Key routes: `/dashboard`, `/resume/*`, `/jobs/*`, `/applications`, `/linkedin/*`, `/email/*`, `/leads`, `/settings/*`.

---

## Build Phases

- Phase 1: Auth + model router + resume upload — ✅ Done
- Phase 2: RAG + Resume Agent + LinkedIn Agent — ✅ Done
- Phase 3: Job Search Agent + PinchTab — ✅ Done
- Phase 4: Gmail MCP + Email/FollowUp Agents — ✅ Done
- Phase 5: Orchestrator + full loop + kanban — ✅ Done
- Phase 6: Next.js frontend + Docker Compose — ✅ Done
- Phase 7: Production hardening + security audit — ✅ Done

---

## Current State (P1–P7 Complete)

All 7 build phases done. Platform production-ready.

| Phase | Status | Tests |
|---|---|---|
| P1: Foundation | ✅ Done | 25 unit |
| P2: RAG Pipeline | ✅ Done | +5 unit |
| P3: Resume + LinkedIn Agents | ✅ Done | +7 unit |
| P4: Job Search + BullMQ | ✅ Done | +3 unit |
| P5: Email + Follow-Up Agents | ✅ Done | +5 unit |
| P6: Orchestrator + Frontend | ✅ Done | +7 unit |
| P7: Production Hardening | ✅ Done | +6 security |

Total: 46 tests (40 unit + 6 security)
