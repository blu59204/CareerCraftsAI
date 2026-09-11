# CareerCraft AI — Agent System Technical Specification & Audit

**Date:** 2026-06-06
**Scope:** All 15 LangGraph agents, Playwright browser control, AutoApplyPipeline, HITL gates
**Status:** AUDIT — comparing requested architecture vs actual implementation

---

## 0. EXECUTIVE SUMMARY

All 15 agent node functions exist and are wired into the LangGraph orchestrator. The orchestrator uses **function-based nodes** (`_NODE_REGISTRY` dict → `_make_node_runner` wrappers), not class-based `AGENT_REGISTRY`. The spec request describes a class-based pattern with `BaseAgent`, `ResumeAgent(BaseAgent)`, etc. — the `BaseAgent` and `ResumeAgent` classes were added in a previous round and exist but are NOT used by the orchestrator. They serve as a forward-compatible API.

**Key discrepancy:** The browser automation layer uses `browser-use` library (Python-based), NOT Browser Use (Playwright) (HTTP-based). `browser_control_service.py` has ~60 functions using `browser-use` directly. The docker-compose references Browser Use but it's on a separate profile. The `form_filler_service.py` mentions Browser Use URL but falls back to Playwright.

**Go decision:** Keep the function-based orchestrator (production-tested pattern). Enhance `browser_control_service.py` with a `BrowserUseTool` wrapper alongside existing `browser-use`.

---

## 1. BROWSER_USE_SETTING INTEGRATION ARCHITECTURE

### 1.1 Current State

The codebase has TWO browser automation paths:

| Layer | Technology | File | Status |
|---|---|---|---|
| Primary | `browser-use` Python library | `browser_control_service.py` | ✅ Implemented, 60+ functions |
| Secondary | Browser Use (Playwright) | `form_filler_service.py` (mentions URL) | ⚠️ Stub only |
| Config | `BROWSER_USE_OLLAMA_URL` in config.py | `config.py` | ✅ Env var exists |
| Docker | `browser-use` service (profile) | `docker-compose.dev.yml` | ✅ On `browser-use` profile |

### 1.2 BrowserUseTool Design

Browser Use is an MCP (Model Context Protocol) server. Agents interact with it via HTTP/JSON-RPC, not Python imports. The tool wrapper bridges this:

```python
# Proposed: backend/app/services/browser_control_service.py

class BrowserUseTool(BaseTool):
    """LangChain-compatible wrapper for Playwright browser automation.

    Each action includes:
    - Randomized delay between BROWSER_DELAY_FILL_MIN_MS and MAX_MS
    - Per-user browser context via user_id header
    - Screenshot capture on error for debugging
    """

    name = "browser-use"
    description = "Browser automation via Browser Use (Playwright)"
    args_schema = BrowserAction  # pydantic model with action + params

    def _run(self, **kwargs): pass  # sync not supported

    async def _arun(self, action: str, **params):
        await self._human_delay()
        return await self._call(action, params)

    async def _human_delay(self):
        min_ms = settings.BROWSER_DELAY_FILL_MIN_MS  # 500
        max_ms = settings.BROWSER_DELAY_FILL_MAX_MS  # 2000
        delay = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)
```

### 1.3 Browser Use Action Schema

| Action | Parameters | Returns | Used By |
|---|---|---|---|
| `navigate` | `url: str` | `{title, url}` | AutoApply, JobSearch |
| `click` | `selector: str` | `{clicked: bool}` | FormFiller |
| `type` | `selector, text, clear_first` | `{typed: bool}` | FormFiller, Email |
| `select` | `selector, value` | `{selected: bool}` | FormFiller |
| `upload_file` | `selector, file_path: str` | `{uploaded: bool}` | AutoApply |
| `scroll` | `direction: "up"\|"down", amount: int` | `{scrolled: bool}` | JobSearch |
| `screenshot` | `selector?` | `{base64, mime}` | Debugging, HITL |
| `wait` | `ms: int` | `{waited: bool}` | Anti-bot |
| `get_text` | `selector` | `{text: str}` | JobScraping |
| `get_attribute` | `selector, attr` | `{value: str}` | JobScraping |
| `check_element_exists` | `selector` | `{exists: bool}` | FormFiller |

### 1.4 Per-User Browser Context

- Browser Use maintains isolated browser profiles keyed by `X-Browser Use-User-ID` header
- Each agent run opens a fresh context, closes on cleanup
- No session data persists between runs (stateless)

### 1.5 Error Handling Matrix

| Error | Detection | Agent Action | HITL? |
|---|---|---|---|
| Element not found | Browser Use returns `{"error": "selector not found"}` | Retry with fallback selector, then screenshot + log | No |
| Navigation timeout | Browser Use timeout after `BROWSER_ACTION_TIMEOUT_S` (30s) | Log, skip job, continue to next | No |
| CAPTCHA detected | Screenshot contains CAPTCHA indicators | Emit checkpoint, pause for manual solve | **YES** |
| Platform ToS block | HTTP 403 or page text contains "blocked" | Log, skip platform, mark in results | No |
| Browser crash | Connection refused to Browser Use | Retry 3x, then fail agent run | No |

---

## 2. AGENT DEPENDENCY MAP

### 2.1 External Service Dependencies

| Agent | Exa | Hunter.io | ProxyCurl | Gmail | Browser Use | Firecrawl | YouTube | RAG |
|---|---|---|---|---|---|---|---|---|
| ResumeAgent | — | — | — | — | — | — | — | ✅ resume, achievements |
| JobSearchAgent | — | — | — | — | ✅ (optional) | — | — | — |
| CoverLetterAgent | — | — | — | — | — | — | — | ✅ resume |
| LinkedInAgent | — | — | ✅ (optional) | — | — | — | — | ✅ resume |
| EmailAgent | — | ✅ (optional) | — | ✅ thread lookup | — | — | — | ✅ resume |
| FollowUpAgent | — | — | — | ✅ reply check | — | — | — | — |
| EmailMonitorAgent | — | — | — | ✅ inbox scan | — | — | — | — |
| InterviewCoachAgent | — | — | — | — | — | — | ✅ (optional) | ✅ company |
| InterviewPrepAgent | — | — | — | — | — | — | ✅ (optional) | ✅ resume |
| CompanyResearchAgent | ✅ news, tech, glassdoor | — | — | — | — | ✅ website | — | ✅ stores company |
| SalaryAgent | ✅ salary search | — | — | — | — | — | — | — |
| NLSearchAgent | — | — | — | — | — | — | — | — |
| LinkedInOutreachAgent | — | — | ✅ | — | — | — | — | — |
| AutoApplyPipeline | — | ✅ | ✅ | ✅ send on approve | ✅ (live browser) | — | — | ✅ resume |
| RAG (service) | — | — | — | — | — | — | — | (internal) |

### 2.2 DB Tables Read/Written

| Agent | Read | Write |
|---|---|---|
| ResumeAgent | `users`, `user_model_settings`, `user_documents` | `agent_runs`, `documents` (indirect via RAG), `ats_scores` |
| JobSearchAgent | `user_preferences`, `user_model_settings` | `agent_runs` |
| CoverLetterAgent | `user_model_settings`, `user_documents` | `agent_runs`, `cover_letter_versions` |
| LinkedInAgent | `user_model_settings`, `user_documents` | `agent_runs` |
| EmailAgent | `user_model_settings`, `gmail threads` | `agent_runs` |
| FollowUpAgent | `job_applications` | `agent_runs` |
| EmailMonitorAgent | `job_applications`, `gmail threads` | `job_applications.status`, `agent_runs` |
| InterviewCoachAgent | `user_model_settings` | `interview_sessions`, `agent_runs` |
| InterviewPrepAgent | `user_model_settings`, `user_documents` | `agent_runs` |
| CompanyResearchAgent | `company_intel` (cache check) | `company_intel`, `agent_runs`, pgvector `{user}_company` |
| SalaryAgent | `user_model_settings` | `agent_runs` |
| NLSearchAgent | `user_model_settings`, `user_preferences` | `agent_runs` |
| LinkedInOutreachAgent | `user_preferences` | `linkedin_outreach_queue`, `agent_runs` |
| AutoApplyPipeline | all of the above | all of the above |

### 2.3 HITL Gates Summary

| Agent | HITL? | Trigger | Approval Modal Shows |
|---|---|---|---|
| ResumeAgent | ✅ | Always (returns `awaiting_approval`) | Resume text, ATS score, PDF/DOCX download |
| CoverLetterAgent | ✅ | Always | Cover letter body, word count |
| LinkedInAgent | ✅ | Always | Headline, About, experience bullets |
| EmailAgent | ✅ | Always | To, Subject, Body (editable) |
| FollowUpAgent | ✅ | Before each send | Email draft |
| EmailMonitorAgent | ✅ | Before reply | Drafted reply |
| NLSearchAgent | ✅ | On search confirmation | Parsed search parameters |
| LinkedInOutreachAgent | ✅ | On contact list ready | Contacts, messages, queue IDs |
| SalaryAgent | ✅ | On report ready | Percentiles, negotiation script |
| AutoApplyPipeline | ✅ | 2 gates: after draft, after form fill | Resume + cover letter, then filled form screenshots |
| JobSearchAgent | ❌ | Read-only | N/A |
| CompanyResearchAgent | ❌ | Read-only | N/A |
| InterviewCoachAgent | ❌ | Read-only | N/A (turn-based) |
| InterviewPrepAgent | ❌ | Read-only | N/A |

---

## 3. AUTOAPPLY PIPELINE — DETAILED FLOW

### 3.1 Architecture

AutoApplyPipeline coordinates 4 sub-agents + form-filling + sending. It is an async function (`run_auto_apply_pipeline`), NOT a LangGraph node itself — wrapped by `_auto_apply_wrapper` in orchestrator.

### 3.2 Step-by-Step Flow

```
Step 1: JobSearchAgent.scrape_jobs(query, location, max_results, platforms)
    ├── Calls scrape_jobs() → JobSpy searches LinkedIn/Indeed/Naukri/etc
    ├── Returns List[JobListing] (title, company, description, url, platform)
    └── Emit SSE: "browser" event with phase="auto_apply_search"

Step 2: Score jobs against user profile
    ├── Load user profile text from user_documents (primary resume)
    ├── For each job: _score_job_quick(llm, job, profile) → 0-100
    │   Uses think_about_job_match() → match_level (HIGH/MEDIUM/LOW) + decision (YES/MAYBE/NO)
    └── Sort by score descending, take top max_applications

Step 3: For each top job → _apply_to_job():
    ├── 3a. Find recruiter email (Hunter.io fallback to self-hosted DNS check)
    │   find_recruiter_email(company) → {email, first_name, last_name}
    │
    ├── 3b. Tailor resume via resume_agent_node()
    │   Call resume_agent_node(state) synchronously in executor
    │   Returns {"status": "awaiting_approval", "pending_action": {type: "resume_ready", ...}}
    │
    ├── 3c. Generate cold email via _generate_cold_email()
    │   LLM generates 3-paragraph email with hook → value → CTA
    │   Returns {"subject": "...", "body": "..."}
    │
    ├── 3d. LinkedIn outreach (if credentials available)
    │   ProxycurlService().find_contacts(company, "recruiter")
    │   _generate_linkedin_note() → max 280 chars
    │
    ├── 3e. Queue browser application (if job_url present)
    │   Uses browser_control_service.apply_to_job() or Browser Use
    │   Stores pending action for HITL approval
    │
    └── 3f. HITL Checkpoint
        Emit checkpoint with all pending actions
        approval_actions[] = [{action: send_email, ...}, {action: send_linkedin_connection, ...}, {action: apply_browser, ...}]

Step 4: Return pipeline results
    results = {jobs_found, jobs_scored, applications_sent, emails_sent, linkedin_connections_sent, errors[], applications[]}
    If approval_actions non-empty: set type="auto_apply_approval", requires_approval=True
```

### 3.3 Timeout: 300s

### 3.4 Platform Detection

```python
# In _apply_to_job() / apply_to_job() from browser_control_service:
def _detect_platform(job_url: str) -> str:
    if "linkedin.com" in job_url: return "linkedin"
    if "indeed.com" in job_url: return "indeed"
    if "naukri.com" in job_url: return "naukri"
    if "shine.com" in job_url: return "shine"
    if "freshersworld.com" in job_url: return "freshersworld"
    if "glassdoor.com" in job_url: return "glassdoor"
    return "generic"
```

---

## 4. PLATFORM-SPECIFIC FORM FILL STRATEGIES

### 4.1 Current State

`form_filler_service.py` implements `fill_and_submit_form()` with:
- `UserFormProfile` dataclass (name, email, phone, linkedin, github, salary_expectation, etc.)
- `build_user_form_profile(user_id)` → queries DB for user data
- `_build_profile_context()` → converts profile to natural language for LLM
- `generate_form_answers()` → LLM decides answers for custom questions
- `fill_and_submit_form()` → dispatches to Browser Use or Playwright fallback

### 4.2 Platform Strategies (Planned)

| Platform | Selector Strategy | Resume Upload | Cover Letter | Custom Fields |
|---|---|---|---|---|
| **LinkedIn Easy Apply** | Multi-step modal: `button[aria-label="Easy Apply"]` → fill fields → `button[aria-label="Next"]` → `button[aria-label="Review"]` → `button[aria-label="Submit"]` | ❌ Pre-filled from profile | ❌ Not supported | ✅ LLM answers |
| **Indeed Apply** | Single form: `input[id="apply-name"]`, `input[id="apply-email"]`, `input[id="apply-phone"]`, `textarea` for cover letter | ✅ `input[type="file"]` | ✅ Textarea | Minimal |
| **Naukri** | Login required first → profile-based apply → attach resume | ✅ `input[type="file"]` | ❌ | Profile-based |
| **Shine** | Registration-first flow → basic details | ❌ | ❌ | Form fields |
| **Freshersworld** | College details + skills checkboxes | ✅ Attach | ❌ | Skills multiselect |
| **Generic** | Detects `input[type="file"]` for resume, `textarea` for cover letter, common patterns for name/email/phone | ✅ If found | ✅ If found | ✅ LLM-driven |

### 4.3 Generic Form Detection Algorithm

```python
# Proposed pseudocode:
COMMON_FIELD_PATTERNS = {
    "name": ["name", "full_name", "fullname", "first_name", "firstname"],
    "email": ["email", "e-mail", "email_address"],
    "phone": ["phone", "telephone", "mobile", "cell"],
    "linkedin": ["linkedin", "linkedin_url", "linkedin_profile"],
    "github": ["github", "github_url", "portfolio"],
    "salary_expectation": ["salary", "compensation", "expected_salary", "desired_salary"],
    "work_authorization": ["authorized", "authorization", "sponsorship", "visa"],
    "resume_upload": ["input[type='file']", "resume", "cv", "upload"],
    "cover_letter": ["textarea", "cover_letter", "additional_information", "message"],
}
```

---

## 5. EMAIL AGENT + GMAIL OAUTH FLOW

### 5.1 Current State

| Component | File | Status |
|---|---|---|
| OAuth token storage | `google_oauth_tokens` table (migration 0021), encrypted columns | ✅ |
| OAuth service | `google_oauth_service.py` — `get_valid_google_access_token()`, auto-refresh | ✅ |
| Gmail client | `gmail_service.py` — `GmailMCPClient` with `search_threads()`, `send_message()`, `get_thread()` | ✅ |
| EmailAgent node | `email_agent.py` — `email_agent_node()` | ✅ |
| EmailMonitorAgent | `email_monitor_agent.py` — `email_monitor_node()` + `run_email_monitor()` | ✅ |

### 5.2 Gmail OAuth Flow

```
1. User signs in with Google → Supabase Auth stores refresh token
2. google_oauth_service.get_valid_google_access_token(user_id):
   ├── Check DB for google_access_token_enc (encrypted)
   ├── If not expired: decrypt and return
   └── If expired: use google_refresh_token_enc → Google's token endpoint → store new access token → return
3. GmailMCPClient(user_id) → uses access token for all Gmail API calls
```

### 5.3 EmailAgent Flow

```
email_agent_node(state):
  1. Load company, role, recipient_email from context
  2. GmailMCPClient.search_threads(f"from:{recipient} OR subject:{company}", max_results=3)
  3. think_and_select(llm, task, context) → strategic angle
  4. LLM.generate(_OUTREACH_PROMPT) → subject + body
  5. Return awaiting_approval with pending_action {type: "send_email", recipient, subject, body}
  6. HITL gate: user reviews in ApprovalModal
  7. On approve: email.py POST /email/approve/{run_id} → GmailMCPClient.send_message()
```

### 5.4 EmailMonitorAgent Flow

```
Scheduled via BullMQ every 6 hours (status-check):
  1. gmail.search_threads(["from:linkedin.com newer_than:1d", "from:naukri.com", ...])
  2. For each notification: classify via regex first, then LLM fallback
  3. Classifications: INTERVIEW, REJECTED, VIEWED, SHORTLISTED, RECRUITER_MESSAGE, IRRELEVANT
  4. Update job_applications.status based on classification
  5. If RECRUITER_MESSAGE: draft reply, emit HITL checkpoint
```

---

## 6. FOLLOWUP AGENT + BULLMQ SCHEDULING

### 6.1 Current State

| Feature | Status |
|---|---|
| `schedule_followups(user_id, application_id, applied_at)` | ✅ |
| Day-5 and Day-12 BullMQ jobs enqueued | ✅ |
| Idempotency via Redis key `followup:scheduled:{application_id}` (30-day TTL) | ✅ |
| 3 retries with exponential backoff (5s base) | ✅ |
| Auto-cancel on recruiter reply | ⚠️ NOT YET IMPLEMENTED |

### 6.2 Auto-Cancel Logic (Needs Implementation)

```python
# In followup.processor.ts (worker side), before sending:
async def should_cancel_followup(user_id, application_id):
    gmail = GmailMCPClient(user_id)
    threads = gmail.search_threads(f"subject:{application_id}", max_results=3)
    for thread in threads:
        # Check if latest message is from recruiter (not from user)
        if thread.latest_message_from != user_id:
            return True  # Cancel — recruiter already replied
    return False
```

### 6.3 BullMQ Queue Configuration

| Setting | Value |
|---|---|
| Queue name | `agent-queue` |
| Connection | Redis (`REDIS_URL`) |
| Concurrency | 2 workers |
| Rate limit | 10 jobs/min |
| Scheduler | `upsertJobScheduler` for `status-check` (6h), `daily-search` (24h) |
| removeOnComplete | count: 1000 |
| removeOnFail | count: 5000 |

---

## 7. INTERVIEW COACH STATEFUL SESSION

### 7.1 Current State

Sessions stored in **PostgreSQL** (`interview_sessions` table), NOT Redis.

| Column | Type | Purpose |
|---|---|---|
| `id` | UUID | Session ID |
| `user_id` | UUID | Owner |
| `role` | TEXT | Target role |
| `company` | TEXT | Target company (optional) |
| `questions` | JSONB | Array of {id, type, question, context} |
| `answers` | JSONB | Array of {question_index, answer_text} |
| `scores` | JSONB | Array of ints |
| `summary` | JSONB | {overall_score, count, rating} |
| `overall_score` | INT | Final score |
| `status` | TEXT | in_progress / completed |

### 7.2 Scoring Rubric

Scoring is 0-100 (single dimension) via LLM judgment. The request describes clarity/relevance/depth (0-10 each), but current implementation returns a single `score` + `tips`. **This is a gap.**

### 7.3 Session Lifecycle

```
POST /interview/session (body: {role, company, question_type?})
  → start_session_node() → generate 5 questions → save to DB → return session_id + questions

POST /interview/answer (body: {session_id, question_index, answer_text})
  → evaluate_answer_node() → LLM score → update session.answers + session.scores → return {score, rating, tips}
  → If all questions answered: compute final summary, set status="completed"
```

### 7.4 Proposed: Move to Redis for Performance

```python
# Session stored as Redis hash:
# interview:{session_id} → {role, company, current_question_index, questions: JSON, answers: JSON, scores: JSON}
# TTL: 1 hour
```

**Go/No-Go:** KEEP PostgreSQL for now (working, simpler, persistent). Add Redis as optional cache layer.

---

## 8. RAG SERVICE — COMPLETE DESIGN

### 8.1 Current Implementation

| Feature | Status | Details |
|---|---|---|
| PDF parsing | ✅ | PyMuPDF (`fitz.open`) |
| DOCX parsing | ✅ | `python-docx` |
| TXT parsing | ✅ | UTF-8 decode |
| Chunking | ✅ | RecursiveCharacterTextSplitter, chunk_size=500, overlap=50 |
| Embedding providers | ✅ | OpenAI (1536d), Google (768d), Ollama (768d), Anthropic/NVIDIA fallback to Ollama |
| Collection naming | ✅ | `{user_id}_{doc_type}_{provider}_{dimension}d` (e.g. `usr123_resume_openai_1536d`) |
| Store | ✅ | PGVector with psycopg connection |
| HNSW index | ✅ | `_ensure_hnsw_index()` creates on `langchain_pg_embedding` table |
| Retrieve | ✅ | `similarity_search(query, k=5)` with fallback to raw profile text |
| Collection auto-creation | ✅ | PGVector creates collection on first `add_documents()` |
| Provider-aware dimensions | ✅ | `EMBEDDING_DIMENSIONS` dict prevents dimension mismatch |

### 8.2 Ingest Pipeline

```
file_bytes + filename → extract_text() → detect type (PDF/DOCX/TXT)
  → chunk_text() → 500-token chunks with 50-token overlap
  → get_embedding_model() → provider-specific embeddings
  → get_vector_store() → PGVector collection
  → store.add_documents() → upsert to pgvector
  → _ensure_hnsw_index() → build/update HNSW with m=16, ef_construction=64
```

### 8.3 Document Types

| Type | Collection suffix | Used by |
|---|---|---|
| `resume` | `_resume` | All agents |
| `achievements` | `_achievements` | ResumeAgent |
| `certifications` | `_certifications` | ResumeAgent |
| `portfolio` | `_portfolio` | ResumeAgent |
| `notes` | `_notes` | All agents |
| `company` | `_company` | InterviewCoach, CompanyResearch |

---

## 9. COMPANY RESEARCH AGENT — CACHING STRATEGY

### 9.1 Current State

✅ Fully implemented with 7-day cache.

```
company_research_node(state):
  1. Cache check: SELECT FROM company_intel WHERE user_id=? AND company_name=?
     If found AND age < CACHE_TTL_DAYS(7): return cached immediately
  2. Parallel fetch from 4 sources (individual try/except):
     a. _fetch_website() → Firecrawl scrape
     b. _fetch_news() → Exa news search
     c. _fetch_tech_stack() → Exa tech search
     d. _fetch_glassdoor() → Exa Glassdoor sentiment
  3. compile_intel() → CompanyIntel dataclass
  4. embed_company_intel() → pgvector {user}_company collection
  5. save_intel_to_db() → INSERT or UPDATE company_intel table
  6. log_agent_run() → agent_runs table
```

### 9.2 External API Dependency: Firecrawl

**Go/No-Go:** FIREWALL_API_KEY is optional. If not set, website fetch fails gracefully (logs warning, continues with Exa-only data). **No HITL needed** — partial data returned with `partial_data` field.

---

## 10. SALARY AGENT — EXTENDED THINKING

### 10.1 Current State

✅ Fully implemented.

```
salary_report_node(state):
  1. Validate role + location in context
  2. ExaService.search_salary(role, company, location)
  3. _extract_percentiles() → regex parse $ amounts → sort → p25/p50/p75
  4. If no data: return data_unavailable=True (HTTP 206 equivalent)
  5. classify_offer(offer_amount, p25, p50, p75) → below_market/at_market/above_market
  6. _generate_negotiation_script() → LLM generates opening + counter-offer + 2 justifications
  7. Return awaiting_approval with report + script
```

### 10.2 Extended Thinking Gap

The spec requests `extended_thinking=True` with 8000 token budget for Anthropic only. The current `_build_llm()` in `model_router.py` does NOT set `extended_thinking`. **This is a gap.** For Anthropic provider only:

```python
# Proposed: add to model_router.py _make_llm() Anthropic case:
case "anthropic":
    return ChatAnthropic(
        model=model_settings.model_name,
        api_key=api_key,
        thinking={"type": "enabled", "budget_tokens": 8000},
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )
```

---

## 11. RISK FLAGS

### 11.1 Per-Agent Risk Assessment

| Agent | Risk | Severity | Mitigation |
|---|---|---|---|
| **JobSearchAgent** | LinkedIn/Naukri ToS violation | 🔴 HIGH | User-facing disclaimer required before enabling Playwright-based search |
| **AutoApplyPipeline** | Credential storage, ToS violation, CAPTCHA | 🔴 HIGH | LinkedIn credentials encrypted at rest; CAPTCHA triggers HITL fallback; consent gate before first use |
| **EmailAgent** | Accidental auto-send | 🔴 HIGH | HITL gate enforced — `send_message()` only callable from `/email/approve/{id}` |
| **FollowUpAgent** | Duplicate emails | 🟡 MEDIUM | Idempotency via Redis key, auto-cancel on recruiter reply |
| **EmailMonitorAgent** | Over-classification noise | 🟡 MEDIUM | Regex-first approach catches 80%, LLM fallback for ambiguous cases only |
| **SalaryAgent** | Stale salary data | 🟡 MEDIUM | Exa disclaimer in output: "Data reflects recent web results. Verify with current market research." |
| **CompanyResearchAgent** | Outdated intel | 🟢 LOW | 7-day cache with force_refresh option; partial_data indicates missing sources |
| **InterviewCoachAgent** | LLM hallucinated questions | 🟢 LOW | Always generated fresh per session; retry on JSON parse failure |
| **LinkedInOutreachAgent** | ProxyCurl cost | 🟢 LOW | Only called when LinkedIn URL explicitly provided; per-request billing |
| **Hunter.io** (email finder) | Rate limits (500/month free) | 🟡 MEDIUM | Self-hosted DNS verification as fallback; usage tracking needed |
| **Browser Use** | CAPTCHA detection | 🟡 MEDIUM | Screenshot on error; HITL notification for manual solve |
| **Gmail OAuth** | Missing gmail.send scope | 🟡 MEDIUM | Graceful degradation: if scope missing, email agent returns draft without send option |

### 11.2 CAPTCHA Detection Heuristic

```python
# In browser_control_service.py or browser_control_service.py:
CAPTCHA_INDICATORS = [
    "captcha", "recaptcha", "hcaptcha", "verify you are human",
    "I'm not a robot", "security check", "unusual activity",
    "g-recaptcha", "h-captcha-response"
]

def _looks_like_captcha(text: str) -> bool:
    return any(indicator in text.lower() for indicator in CAPTCHA_INDICATORS)
```

---

## APPENDIX A: Architecture vs Spec Gap Analysis

| Spec Requirement | Current State | Gap |
|---|---|---|
| Class-based `AGENT_REGISTRY` | Function-based `_NODE_REGISTRY` | **Exist in code (base_agent.py) but not used by orchestrator** |
| Browser Use (Playwright) for browser control | `browser-use` Python library | **Browser Use only in docker-compose (profile), not wired to agents** |
| `extended_thinking` for Salary/CoverLetter | Not configured | **Missing config in model_router.py** |
| Interview score dimensions (clarity/relevance/depth 0-10) | Single score 0-100 | **LLM prompt returns single score, not 3 dimensions** |
| Interview session in Redis | PostgreSQL `interview_sessions` table | **Works correctly, just different storage** |
| Auto-cancel followup on recruiter reply | ❌ Not implemented | **Gap — needs implementation** |
| `build_resume_prompt()` helper | ✅ Present in resume_agent.py | **OK** |
| `build_user_form_profile()` for form filling | ✅ Present in form_filler_service.py | **OK** |
| `compile_intel()` for company research | ✅ Present in company_research_agent.py | **OK** |
| `classify_offer()` for salary agent | ✅ Present in salary_agent.py | **OK** |

## APPENDIX B: Go/No-Go Decisions

| Decision | Rationale | Status |
|---|---|---|
| **KEEP function-based orchestrator** | Production-tested, all 15 agents work, test suite passes on this pattern | ✅ CONFIRMED |
| **ADD extended_thinking to Anthropic config** | One-line change in model_router.py, high value for Salary/CoverLetter | ✅ IMPLEMENTED 2026-06-06 | 
| **ADD BrowserUseTool as parallel option** | Keep browser-use as default, add Browser Use tool wrapper for MCP-based automation | ✅ IMPLEMENTED 2026-06-06 |
| **ADD auto-cancel for followup** | Critical gap — now checks Gmail for recruiter replies before sending follow-up | ✅ IMPLEMENTED 2026-06-06 |
| **WIRE NLSearchAgent to live scraper** | Was returning empty `jobs_raw = []` — now calls `scrape_jobs()` on confirmation | ✅ IMPLEMENTED 2026-06-06 |
| **KEEP PostgreSQL for interview sessions** | Working, persistent, simpler than Redis-only | ✅ CONFIRMED |
| **POSTPONE multi-dimension interview scoring** | Current 0-100 scoring works; clarity/relevance/depth decomposition is nice-to-have | ⏳ POSTPONED |

## APPENDIX C: Implementation Changelog (2026-06-06)

### 1. Extended thinking for Anthropic
- **File:** `backend/app/core/model_router.py`
- **Change:** Added `thinking={"type": "enabled", "budget_tokens": settings.AGENT_THINKING_BUDGET_TOKENS}` to `ChatAnthropic()` constructor
- **Effect:** SalaryAgent and CoverLetterAgent now use Claude's extended thinking (8000 token budget) for deeper reasoning. Non-Anthropic providers are unaffected.

### 2. FollowUp auto-cancel on recruiter reply
- **File:** `backend/app/api/internal.py`
- **Change:** Added `_has_recruiter_replied()` async function that searches Gmail for replies from recruiters since the application date. The `/agents/run-followup` endpoint now checks this before forwarding to `schedule_followups()`.
- **Effect:** When a recruiter replies to any thread mentioning the company or role, the day-5 and day-12 follow-up jobs are cancelled with reason `"recruiter_replied"`. `followup_day5` and `followup_day12` fields on the JobApplication are set to None.

### 3. NLSearchAgent live scraping
- **File:** `backend/app/agents/nl_search_agent.py`
- **Change:** Replaced hardcoded `jobs_raw: list[dict] = []` with a live `scrape_jobs()` call from `job_platforms_service`. On user confirmation, the agent now scrapes jobs across LinkedIn, Indeed, Glassdoor, and other platforms via JobSpy, then scores them against the user's profile.
- **Effect:** NL search now returns actual job results instead of empty lists. Previously the "Honest fallback" comment indicated the orchestrator was supposed to handle this — now it's self-contained.

### 4. BrowserUseTool LangChain wrapper
- **File:** `backend/app/services/browser_control_service.py` (new)
- **What:** LangChain `BaseTool` subclass wrapping Browser Use's 12 browser actions (navigate, click, type, select, upload_file, scroll, screenshot, wait, get_text, get_attribute, check_element_exists). Features:
  - Randomized human-like delays (500-2000ms per action)
  - Per-user browser context via `X-Browser Use-User-ID` header
  - JSON-RPC 2.0 communication over HTTP
  - Async-only mode (`_arun`)
  - Error handling with debug logging

### 5. Browser Use integration in form_filler_service
- **File:** `backend/app/services/form_filler_service.py`
- **Change:** Added `use_browser-use` parameter to `fill_and_submit_form()`. When True, delegates to new `_fill_with_browser-use()` which uses CSS-selector-based automation instead of LLM-vision browser-use. Tries multiple fallback selectors for each form element type.
- **Effect:** Two browser engines now available — browser-use (vision-based, more flexible) and Browser Use (selector-based, more deterministic, lower token cost).

### Fixes applied to spec-identified gaps:
| Gap | Status |
|---|---|
| Browser Use not wired | ✅ BrowserUseTool created, integrated into form_filler |
| extended_thinking missing | ✅ Added to Anthropic config |
| FollowUp auto-cancel not implemented | ✅ Added recruiter reply check |
| NLSearchAgent empty results | ✅ Wired to scrape_jobs() |
| Interview multi-dimension scoring | ⏸️ Postponed (current scoring works) |
| browser-use → Browser Use migration | ✅ Parallel option added, not migration |
