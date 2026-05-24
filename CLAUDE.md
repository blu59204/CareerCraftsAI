# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

**Auth** — Clerk (Google OAuth + email). Google OAuth scopes: Gmail read/send + Drive read/write only.

---

## Tech Stack Quick Reference

| Concern | Choice |
|---|---|
| Frontend | Next.js 14 App Router + Tailwind + shadcn/ui + Zustand + TanStack Query v5 |
| Backend | FastAPI 0.111+ / Python 3.12 |
| Agents | LangGraph 0.2+ / LangChain 0.3+ |
| Primary LLM | claude-sonnet-4-6 |
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
pytest                          # all tests
pytest tests/test_resume.py     # single file
pytest -k "test_name"           # single test
```

### Docker (full stack)
```bash
docker compose up --build       # start all services
docker compose up frontend backend  # specific services
docker compose logs -f backend  # tail logs
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

Project not yet built (as of May 2026). Planned 10-week build:
- Phase 1: Auth + model router + resume upload
- Phase 2: RAG + Resume Agent + LinkedIn Agent  
- Phase 3: Job Search Agent + PinchTab
- Phase 4: Gmail MCP + Email/FollowUp Agents
- Phase 5: Orchestrator + full loop + kanban
- Phase 6: Production hardening
