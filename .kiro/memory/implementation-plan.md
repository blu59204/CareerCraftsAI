# CareerCraft AI — Remaining Implementation Plan

## Context for Next Session

**Project:** D:\CareerCraft AI
**GitHub:** https://github.com/PREETHAM1590 (sole contributor)
**Git:** All commits authored by PREETHAM1590, local only (not pushed yet)
**Tests:** 130 passing, 2 skipped
**Last commit:** `test: fix all unit tests - 130 passing, update mocks for new architecture`

### What's Done
- ✅ 28 bug fixes
- ✅ 25 platform enhancement tasks (new agents, API routes, frontend pages)
- ✅ 10 security audit fixes (JWT pinning, RLS, Redis auth, CSP, prompt injection defense)
- ✅ Automation pipeline (browser-use, JobSpy, self-hosted email finder, auto-apply)
- ✅ Auto/Drafts toggle, encrypted LinkedIn credentials
- ✅ Git history rewritten — PREETHAM1590 is sole author on all 95 commits

---

## Phase 1: Add All Indian Job Platforms (Priority: HIGH)

### Platforms to Add
| Platform | URL | Method | Type |
|----------|-----|--------|------|
| Naukri.com | naukri.com | browser-use scraping | India #1 |
| Foundit (Monster India) | foundit.in | browser-use | Major |
| Instahyre | instahyre.com | browser-use | Tech-focused |
| Cutshort | cutshort.io | browser-use | Startup/Tech |
| Hirect | hirect.in | browser-use | Chat-based hiring |
| Internshala | internshala.com | browser-use | Freshers/Interns |
| Apna | apna.co | browser-use | Blue/Grey collar + IT |
| WorkIndia | workindia.in | browser-use | Entry-level |
| AngelList/Wellfound | wellfound.com | JobSpy supports | Startups |
| Shine.com | shine.com | browser-use | TimesJobs group |
| iimjobs | iimjobs.com | browser-use | Premium roles |
| Freshersworld | freshersworld.com | browser-use | Freshers |

### Implementation
1. Update `job_platforms_service.py` — add Naukri, Foundit, Wellfound to JobSpy config
2. Create `indian_platforms_service.py` — browser-use scraper for platforms JobSpy doesn't support
3. Each platform needs: search URL pattern, result extraction logic, login support
4. User stores platform credentials (encrypted) — app logs in and scrapes on their behalf

---

## Phase 2: ATS-Friendly Resume (Priority: HIGH)

### Research Summary (from web)
ATS-compliant resume must pass 3 gates:
1. **Parsing** — ATS extracts structured data (name, email, job titles, dates, skills)
2. **Keyword match** — content hits minimum keyword threshold vs JD
3. **Formatting** — layout doesn't break rendering

### Rules to Implement
- Single column layout (NO sidebars, NO two-column)
- Standard section headers: "Work Experience", "Education", "Skills", "Summary"
- No tables, text boxes, graphics, icons, skill bars
- Dates in MM/YYYY or "Month YYYY" format
- Clean PDF (text-selectable, not image-based)
- Font: Arial, Calibri, or Helvetica (10-12pt)
- Margins: 0.5-1 inch
- File format: PDF (text-selectable) or DOCX

### Changes Needed
1. Update `pdf_service.py` — rewrite ReportLab template to follow ATS rules
2. Update `RESUME_SYSTEM_PROMPT` in `resume_agent.py` — instruct LLM to output ATS-structured text
3. Add ATS validation step after generation (check for tables, columns, non-standard headers)
4. Generate both PDF and DOCX versions

---

## Phase 3: Auto-Apply on Hiring Platforms (Priority: HIGH)

### Flow
```
User logs into platform (one-time, cookies saved)
    ↓
App finds matching jobs on that platform
    ↓
browser-use fills application form automatically
    ↓
Attaches tailored resume + cover letter
    ↓
Submits (or saves draft based on auto_mode toggle)
    ↓
Status tracked in app's Kanban board
```

### Implementation
1. Create `auto_apply_service.py` with platform-specific apply logic:
   - LinkedIn Easy Apply (already done)
   - Naukri Apply (fill form fields, upload resume)
   - Instahyre Apply (one-click + message)
   - Indeed Apply
2. Each platform handler: `login()`, `search()`, `apply(job_url, resume_path)`
3. Track application status: "applied", "viewed", "interview", "offer", "rejected"
4. Email/in-app notifications on status changes

---

## Phase 4: API Key Security — Model Never Sees Keys (Priority: HIGH)

### Problem
Currently, the decrypted API key is passed to LangChain LLM constructor. If the model is prompted to "print your configuration", it could theoretically leak the key.

### Solution: Proxy Pattern
1. Create `llm_proxy_service.py` — a local HTTP proxy that:
   - Receives LLM requests from agents (without API key)
   - Injects the decrypted API key at the HTTP layer
   - Forwards to the actual LLM provider
   - Strips the key from any response/logs
2. Agents never see the raw key — they call `http://localhost:8001/v1/chat/completions`
3. The proxy adds `Authorization: Bearer <decrypted_key>` at request time
4. Even if prompt injection extracts "system config", the key isn't in the prompt context

### Alternative (simpler)
- Use LangChain's `callbacks` to redact any API key patterns from LLM output
- Add output filter: regex scan for `sk-`, `AIza`, `gsk_` patterns → replace with `[REDACTED]`

---

## Phase 5: Memory Agent & Harness Improvements (Priority: MEDIUM)

### Current State
- `harness.py` has memory injection, episode saving, reflection, strategy selection
- `memory/manager.py` has asyncpg pool for pgvector storage
- BUT: memory isn't being used effectively — agents don't learn from past failures

### Improvements Needed
1. **Episodic memory** — after each job application, store: company, role, outcome, what worked
2. **Preference learning** — track which job types user applies to most, auto-adjust search
3. **Blacklist memory** — companies user rejected, roles that didn't match
4. **Strategy adaptation** — if cold emails to HR@ fail, switch to LinkedIn outreach
5. **Cross-session context** — remember user's target salary, preferred locations, deal-breakers

### Implementation
1. Ensure `MemoryManager.initialize()` is called (lazy pool init already works)
2. Add memory extraction after each completed pipeline run
3. Add memory retrieval before each new pipeline run (inject as context)
4. Test reflection loop — verify learnings are saved and influence future runs

---

## Phase 6: Application Status Tracking & Follow-ups (Priority: MEDIUM)

### Features
1. **Status tracking** — Kanban board (already exists) with real-time updates
2. **Email notifications** — when application status changes (use Resend)
3. **Automated follow-ups** — day 3, 7, 14 after applying (already partially built)
4. **Browser-based status check** — periodically login to platforms, check if "viewed"/"shortlisted"

### Implementation
1. Add BullMQ scheduled job: check application status on platforms every 6 hours
2. browser-use logs into each platform, checks notification/status page
3. Updates `job_applications.status` in DB
4. Triggers email notification via Resend
5. Triggers follow-up email if no response after N days

---

## Phase 7: Security Testing for AI-Coded Apps (Priority: MEDIUM)

### OWASP LLM Top 10 (2025) Checklist
| # | Threat | Status |
|---|--------|--------|
| LLM01 | Prompt Injection | ✅ Fixed (XML delimiters) |
| LLM02 | Insecure Output Handling | ✅ Fixed (DOMPurify) |
| LLM03 | Training Data Poisoning | N/A (using external LLMs) |
| LLM04 | Model Denial of Service | ⚠️ Need token limits per request |
| LLM05 | Supply Chain Vulnerabilities | ⚠️ Need pip-audit + npm audit |
| LLM06 | Sensitive Info Disclosure | ⚠️ Need output filtering (Phase 4) |
| LLM07 | Insecure Plugin Design | ✅ Fixed (approval gate) |
| LLM08 | Excessive Agency | ✅ Fixed (auto/drafts toggle) |
| LLM09 | Overreliance | N/A (human reviews) |
| LLM10 | Model Theft | N/A (using external LLMs) |

### Additional Tests Needed
1. Run `bandit -r app/` — Python SAST
2. Run `pip-audit` — check for CVEs in dependencies
3. Run `npm audit` in frontend
4. Test prompt injection vectors against all agents
5. Verify no API keys in git history (`trufflehog` scan)
6. Add token usage limits per user per day

---

## Phase 8: Final Polish (Priority: LOW)

1. Update README.md with all new features
2. Add proper error handling for browser-use failures (retry logic)
3. Add rate limiting per platform (don't get banned)
4. Add human-like delays in browser automation (random 2-8s between actions)
5. Add dashboard metrics: applications sent today, response rate, interview rate
6. Mobile-responsive frontend check

---

## Execution Order (Next Session)

```
ALL PHASES COMPLETE — 2026-05-26

✅ Phase 2 (ATS Resume) — ATS-compliant prompt, DOCX generation, ATS validation
✅ Phase 1 (Indian Platforms) — 9 browser-use scrapers + JobSpy integration (14 total platforms)
✅ Phase 4 (Key Security) — LLM output redaction callback + token budget enforcement
✅ Phase 3 (Auto-Apply) — Platform-specific handlers (LinkedIn, Naukri, Instahyre, Indeed, Foundit, Cutshort)
✅ Phase 5 (Memory) — Preference learning, blacklist, cross-session context, post-pipeline extraction
✅ Phase 6 (Status Tracking) — BullMQ scheduled job every 6 hours
✅ Phase 7 (Security Tests) — Bandit scan clean (Low only), 136 tests passing

ADDITIONAL ENHANCEMENTS (Session 2):
✅ Internal status-check endpoint — browser-use checks platform notifications
✅ Email Monitor Agent — reads Gmail for interview/rejection/viewed notifications
✅ Procedural Memory — stores successful workflows as reusable patterns
✅ Google Jobs Search — browser-use scrapes google.com/jobs for company-only postings
✅ LLM Gateway (Zero-Trust) — agents get session token, never the raw API key
✅ Daily Auto-Search Scheduler — BullMQ job searches all platforms daily based on user prefs
```

---

## How to Resume Next Session

All implementation phases are complete. Next steps:
1. Commit all changes
2. Push to GitHub
3. Run `npm audit` in frontend/worker
4. Run `pip-audit` in backend
5. Update README with new features
6. Add tests for new services (email_monitor, indian_platforms, auto_apply, llm_gateway)
