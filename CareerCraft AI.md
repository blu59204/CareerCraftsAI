# Product Requirements Document: JobAgent AI

**Agentic Job Search & Application Automation Platform**  
**Version:** 1.0 - May 2026  
**Status:** Confidential Internal Use Only - v1.0 Draft

---

## 1. Executive Summary

JobAgent AI is a full-stack, multi-agent AI platform that automates the end-to-end job search process: discovering relevant roles, generating tailored resumes and cover letters, submitting applications, managing recruiter communications, and optimizing LinkedIn profiles — all powered by user-selected AI models via their own API keys.

| Attribute | Detail |
|---|---|
| Product Name | JobAgent AI |
| Version | 1.0 |
| Status | Draft |
| Date | May 2026 |
| Target Launch | Q4 2026 |

### 1.1 Problem Statement

Job seekers spend 5-10 hours per application manually tailoring resumes, writing cover letters, researching companies, and tracking follow-ups. ATS systems reject 75% of resumes before human review. Most candidates apply with generic documents and never follow up.

### 1.2 Solution

JobAgent AI deploys a harness of specialized AI agents — each owning a specific part of the job search workflow — orchestrated by a supervisor agent. Users bring their own AI API keys (Claude, GPT, Gemini, Ollama, NVIDIA NIM), pay only for what they use, and retain full control over their data.

---

## 2. System Architecture

### 2.1 High-Level Architecture

The platform follows a 4-layer architecture: Presentation Layer (Next.js), API Gateway (FastAPI), Agent Harness (LangGraph), and Infrastructure Layer (PostgreSQL + pgvector + Redis + PinchTab).

```text
PRESENTATION LAYER
Next.js 14 App Router + Tailwind CSS
Dashboard | Resume | Jobs | LinkedIn | Email | Settings
|
API GATEWAY
FastAPI (Python 3.12)
/agents | /users | /jobs | /resume | /gmail | /rag
|
AGENT HARNESS (LangGraph)
+------------------+ +--------------+ +-------------+ +----------+
| Orchestrator     | | Job Search   | | Resume      | | LinkedIn |
| (Supervisor)     | | Agent        | | Agent       | | Agent    |
+------------------+ +--------------+ +-------------+ +----------+
+------------------+ +--------------+ +-----------------------------+
| Email Agent      | | Follow-Up    | | RAG Retrieval Agent         |
| (Gmail MCP)      | | Agent        | | (pgvector + Supabase)       |
+------------------+ +--------------+ +-----------------------------+
+---------------------------------------------------------------+
| Model Router                                                  |
| Claude | GPT-4o | Gemini | Ollama | NVIDIA NIM                 |
| (user-provided API keys)                                      |
+---------------------------------------------------------------+
|                    |                    |
PostgreSQL+pgvector Redis+BullMQ         PinchTab Browser
(Supabase)          (job queues)          (LinkedIn/Naukri)
```

### 2.2 Agent Harness Detail

| Agent | Role | Tools Used | Model |
|---|---|---|---|
| Orchestrator | Supervisor — routes tasks, manages state | All sub-agent tools | Claude Sonnet / GPT-4o |
| Job Search Agent | Browse job boards, score matches | PinchTab MCP, Exa.ai | Any (user choice) |
| Resume Agent | Rewrite resume per JD using RAG | pgvector retrieval, PDF gen | Any (user choice) |
| LinkedIn Agent | Rewrite headline, about, bullets | PinchTab MCP, RAG | Any (user choice) |
| Email Agent | Read/send Gmail, draft outreach | Gmail MCP, Drive MCP | Any (user choice) |
| Follow-Up Agent | Track and trigger follow-ups | BullMQ scheduler, Gmail MCP | Any (user choice) |
| RAG Agent | Retrieve context from user docs | pgvector, Supabase | Embedding model |

---

## 3. Navigation Flow

### 3.1 Page Structure

```text
Root (/)
/auth
  /auth/login        -> Google OAuth / Email login
  /auth/register     -> New account + model setup
/dashboard           -> Overview: stats, pipeline, recent activity
/resume
  /resume/upload     -> Upload existing resume (PDF/DOCX)
  /resume/builder    -> AI resume builder from scratch
  /resume/optimize   -> Paste JD -> AI rewrites resume
  /resume/versions   -> All saved resume versions
/jobs
  /jobs/search       -> Search with filters; agent finds matches
  /jobs/matches      -> AI-scored matches for user profile
  /jobs/[id]         -> Job detail + apply with AI assist
/applications        -> Full pipeline (kanban board)
/applications/[id]   -> Single application detail + history
/linkedin
  /linkedin/audit    -> Score current LinkedIn profile
  /linkedin/optimize -> AI rewrites each section
/email
  /email/inbox       -> Read recruiter emails (Gmail MCP)
  /email/compose     -> AI-generate outreach / follow-up
  /email/templates   -> Saved AI-generated templates
/leads               -> Recruiter CRM (track contacts)
/settings
  /settings/models   -> API key per model provider
  /settings/gmail    -> Google OAuth for Gmail
  /settings/profile  -> User preferences
```

### 3.2 User Journey Flow

```text
New User
|
v
Register -> Connect Gmail -> Upload Resume -> Set AI Model
|
v
Dashboard
|
|---> Resume Optimize -> Paste JD -> AI rewrites -> Download PDF
|
|---> Job Search -> Agent browses LinkedIn/Naukri -> Scored list
|     |
|     +---> Select Job -> AI generates resume + cover letter
|     |
|     +---> Apply (PinchTab auto-fills form)
|     |
|     +---> Application saved to pipeline
|
|---> Applications (Kanban: Applied -> Viewed -> Interview -> Offer)
|     |
|     +---> Follow-Up Agent auto-emails at day 5 and day 12
|
+---> LinkedIn Optimizer -> Agent rewrites profile sections
```

---

## 4. Data Flow

### 4.1 Resume Generation Flow

```text
User pastes Job Description
|
v
Resume Agent receives JD text
|
|---> pgvector query: top 5 chunks from user resume
|---> pgvector query: similar past JDs
+---> pgvector query: certifications / portfolio
|
v
LLM prompt assembled:
  system: "You are a professional resume writer..."
  context: [retrieved chunks from pgvector]
  user: "Rewrite resume for this JD using Google XYZ formula"
|
v
LLM generates tailored resume text
|
v
PDF generated (ReportLab) + stored in Supabase Storage
|
v
Version saved to user_resumes table
|
v
User downloads / agent uses for auto-apply
```

### 4.2 Auto-Apply Flow

```text
User triggers "Apply to top 10 jobs"
|
v
BullMQ job queue receives task
|
v
Job Search Agent (PinchTab)
1. pinchtab__navigate -> linkedin.com/jobs
2. pinchtab__fill -> search filters (title, location)
3. pinchtab__snapshot -> get job list (800 tokens/page)
4. Score each job vs user profile (LLM)
5. Return top 10 matches
|
v
For each job (human-in-loop pause):
  Resume Agent -> tailored resume
  Email Agent -> custom cover note
  User reviews -> approves
|
v
PinchTab submits application:
  pinchtab__navigate -> job apply URL
  pinchtab__fill -> resume, cover letter fields
  pinchtab__action -> click Submit
|
v
Application logged to job_applications table
Follow-Up Agent schedules day-5 and day-12 emails
```

### 4.3 RAG Ingestion Flow

```text
User uploads document (resume / cert / portfolio / JD)
|
v
File stored in Supabase Storage (S3-compatible)
|
v
Text extracted: PyMuPDF (PDF) / python-docx (DOCX)
|
v
RecursiveCharacterTextSplitter
  chunk_size: 500 tokens, chunk_overlap: 50 tokens
|
v
Embedding model (user chosen provider):
  OpenAI -> text-embedding-3-small
  Google -> models/embedding-001
  Ollama -> nomic-embed-text (local/free)
  Claude -> fallback to nomic-embed-text
|
v
Vectors stored in pgvector
  collection: {user_id}_{doc_type}
  e.g. "usr_abc123_resume"
|
v
Metadata saved to user_documents table
```

---

## 5. Database Schema

### 5.1 Core Tables

#### users

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  full_name TEXT,
  avatar_url TEXT,
  google_id TEXT UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### user_model_settings

```sql
CREATE TABLE user_model_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL, -- anthropic|openai|google|ollama|nvidia_nim
  api_key_enc TEXT, -- AES-256 encrypted
  model_name TEXT, -- e.g. claude-sonnet-4-6
  ollama_url TEXT, -- for local Ollama
  is_active BOOLEAN DEFAULT true
);
```

#### user_documents

```sql
CREATE TABLE user_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  doc_type TEXT NOT NULL, -- resume|jd|cert|portfolio|cover_letter
  filename TEXT NOT NULL,
  storage_path TEXT NOT NULL, -- Supabase Storage path
  raw_text TEXT,
  embedded_at TIMESTAMPTZ,
  is_primary BOOLEAN DEFAULT false
);
```

#### job_applications

```sql
CREATE TABLE job_applications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  company TEXT NOT NULL,
  role TEXT NOT NULL,
  job_url TEXT,
  jd_text TEXT,
  match_score INTEGER, -- 0-100 AI match score
  resume_id UUID REFERENCES user_documents(id),
  cover_letter TEXT,
  status TEXT DEFAULT "saved",
  -- saved|applied|viewed|interview|offer|rejected
  applied_at TIMESTAMPTZ,
  followup_day5 TIMESTAMPTZ,
  followup_day12 TIMESTAMPTZ,
  notes TEXT
);
```

#### leads (recruiter CRM)

```sql
CREATE TABLE leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  name TEXT,
  email TEXT,
  company TEXT,
  linkedin_url TEXT,
  status TEXT DEFAULT "cold", -- cold|warm|replied|converted
  last_contact TIMESTAMPTZ,
  notes TEXT
);
```

#### agent_runs (audit log)

```sql
CREATE TABLE agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  agent_type TEXT NOT NULL, -- orchestrator|job_search|resume|...
  status TEXT DEFAULT "running", -- running|completed|failed
  input JSONB,
  output JSONB,
  tokens_used INTEGER,
  duration_ms INTEGER,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);
```

#### pgvector — RAG collections

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Managed automatically by LangChain PGVector class
-- Naming: {user_id}_{doc_type}
--
-- usr_abc123_resume    -> user resume chunks
-- usr_abc123_jd        -> past job descriptions
-- usr_abc123_documents -> certs, portfolios
-- usr_abc123_company   -> company intel
-- global_job_market    -> shared market RAG
```

---

## 6. Tech Stack

### 6.1 Full Stack Reference

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| Frontend | Next.js | 14 App Router | Full-stack React framework |
| Frontend | Tailwind CSS | 3.x | Utility-first styling |
| Frontend | shadcn/ui | Latest | Component library |
| Frontend | Zustand | 4.x | Client state management |
| Frontend | TanStack Query | 5.x | Server state & caching |
| Backend | FastAPI | 0.111+ | Python async API framework |
| Backend | Python | 3.12 | Backend language |
| Agent | LangGraph | 0.2+ | Multi-agent orchestration |
| Agent | LangChain | 0.3+ | LLM abstraction + tools |
| AI | Claude (Anthropic) | claude-sonnet-4-6 | Primary LLM |
| AI | GPT (OpenAI) | gpt-4o | Alternative LLM |
| AI | Gemini (Google) | gemini-2.0-flash | Alternative LLM |
| AI | Ollama | Local | Self-hosted open models |
| AI | NVIDIA NIM | API | NVIDIA-hosted models |
| Browser | PinchTab | 0.7.6 | HTTP browser control for agents |
| Database | PostgreSQL | 16 | Primary database |
| Database | pgvector | 0.7+ | Vector embeddings for RAG |
| Database | Supabase | Cloud/Self-host | DB + Auth + Storage + pgvector |
| Cache | Redis | 7.x | Cache + pub/sub |
| Queue | BullMQ | 5.x | Agent job queue |
| Storage | Supabase Storage | S3-compatible | Resume PDFs, uploads |
| Auth | Clerk | Latest | User auth + Google OAuth |
| Email (read/send) | Gmail MCP | Official | Read/send Gmail |
| Files | Google Drive MCP | Official | Resume storage |
| PDF | ReportLab | 4.x | Generate resume PDFs |
| Parse | PyMuPDF + python-docx | Latest | Parse uploaded docs |
| Email (send) | Resend | Latest | Transactional email |
| Proxy | Nginx | Latest | Reverse proxy + SSL |
| Containers | Docker + Compose | Latest | Service orchestration |
| Hosting | Ubuntu VPS | 22.04 LTS | Your own server |

### 6.2 External APIs & MCP Connectors

| Service | Type | Use Case | Cost |
|---|---|---|---|
| Gmail MCP | MCP Connector | Read inbox, send emails, search threads | Free (Google Workspace) |
| Google Drive MCP | MCP Connector | Store and retrieve resume files | Free (15GB) |
| Supabase MCP | MCP Connector | DB management, pgvector, auth | Free tier available |
| PinchTab | Open source binary | Browser automation for job boards | Free (MIT) |
| Exa.ai | REST API | Semantic search for company research | ~$10/mo starter |
| Proxycurl | REST API | LinkedIn profile data via API | ~$0.01/profile |
| Hunter.io | REST API | Find recruiter email addresses | Free 25/mo |
| Firecrawl | REST API | Clean web scraping for RAG ingestion | ~$15/mo starter |
| Resend | REST API | Transactional email delivery | Free 3000/mo |

### 6.3 Infrastructure (Docker Compose)

```yaml
services:
  frontend: # Next.js -> port 3000
  backend:  # FastAPI -> port 8000
  pinchtab: # PinchTab -> port 9867
  redis:    # Redis -> port 6379
  worker:   # BullMQ worker (Node.js)
  nginx:    # Reverse proxy -> 80/443

# Database: Supabase (managed) OR self-hosted PostgreSQL + pgvector
```

---

## 7. Build Phases & Timeline

| Phase | Deliverable | Duration | Key Tech |
|---|---|---|---|
| Phase 1 | Auth + user settings + model router + resume upload | 2 weeks | Next.js, FastAPI, Supabase, Clerk |
| Phase 2 | RAG pipeline + Resume Agent + LinkedIn Agent | 2 weeks | pgvector, LangGraph, LangChain |
| Phase 3 | Job Search Agent + PinchTab browser automation | 2 weeks | PinchTab, BullMQ, Redis |
| Phase 4 | Gmail MCP + Email Agent + Follow-Up Agent | 1 week | Gmail MCP, Google Drive MCP |
| Phase 5 | Orchestrator + full agent loop + kanban dashboard | 2 weeks | LangGraph supervisor, Next.js |
| Phase 6 | Scale testing + proxy setup + production hardening | 1 week | Nginx, Docker, rotating proxies |

**Total Timeline:** 10 weeks from kickoff to production-ready v1.0. Phase 1-2 can be demoed for early user feedback before completing automation features.

---

## 8. Security & Compliance

- All user API keys encrypted at rest with AES-256 before storing in database.
- Google OAuth scopes limited to Gmail read/send and Drive read/write only.
- PinchTab browser profiles isolated per user — no cookie sharing between accounts.
- All agent actions logged to `agent_runs` table for full audit trail.
- Human-in-the-loop gate before any email send or job application submission.
- Rate limiting on all FastAPI endpoints (`slowapi`).
- HTTPS enforced via Nginx + Certbot (Let's Encrypt).
- LinkedIn/Naukri automation may violate platform ToS — user operates under own account and accepts risk.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| LinkedIn blocks PinchTab automation | High | Rotating proxies, human-like delays, stealth mode, session reuse |
| LLM API costs at scale | Medium | User pays own API keys; add per-user token limits in settings |
| Gmail OAuth revocation | Medium | Detect 401 errors, prompt re-auth gracefully in UI |
| pgvector slow at scale | Low | Add HNSW index; partition vectors by user_id |
| BullMQ queue backlog | Medium | Separate worker pods; max concurrency per user = 2 |

---

JobAgent AI - PRD v1.0 - Confidential - May 2026
