# CareerCraft AI — Agent Troubleshooting Guide

Common failure modes and resolution steps for all 15 agents, Playwright browser automation, Gmail OAuth, RAG, HITL gates, and Temporal.

---

## Browser Automation (Playwright/Chromium)

| Symptom | Cause | Fix |
|---|---|---|
| `Element not found: .jobs-apply-button` | LinkedIn UI changed CSS selectors | Screenshot on failure for debugging. Update selectors in `platform_detector.py` |
| CAPTCHA detected during form fill | LinkedIn anti-bot protection triggered | Screenshot captured. Retry with fresh browser context. Notify user via SSE `checkpoint` event — manual solve required |
| Browser context leaking between users | Missing `user_id` parameter | Each request must pass `user_id` parameter for context isolation |

---

## Gmail and Drive via Nango

| Symptom | Likely cause | Fix |
|---|---|---|
| `Gmail not connected` | No active Nango Gmail connection | Connect Gmail in Integrations and wait for the verified status. |
| Connection fails | Missing provider config key or Nango credentials | Verify `NANGO_PROVIDER_CONFIG_KEYS`, `NANGO_SECRET_KEY`, and webhook setup. |
| Gmail API error | Provider scope or Nango proxy error | Reconnect with the required Gmail scopes in Nango and inspect Nango logs. |
| Email draft generated but not sent | HITL gate | Approve the email through the normal approval flow. |

## RAG (Retrieval Augmented Generation)

| Symptom | Cause | Fix |
|---|---|---|
| `pgvector collection not found` | Collection auto-created but pgvector extension missing | Run in Supabase SQL Editor: `CREATE EXTENSION IF NOT EXISTS vector` |
| `No chunks returned for retrieve` | User hasn't uploaded any documents | Upload a resume PDF/DOCX/TXT via the Documents page before using agents that need RAG |
| Embedding model unavailable | Anthropic/NVIDIA users need local Ollama with `nomic-embed-text` | `ollama pull nomic-embed-text`. Ensure Ollama is running at `localhost:11434` |
| OpenAI embedding dimension mismatch | User switched from OpenAI (1536d) to Google (768d) without re-embedding | Collections are namespaced by provider+dimension (`{user}_{type}_{provider}_{dim}d`). Re-upload documents after switching |
| `HNSW index creation failed` | Insufficient disk space or PostgreSQL memory | Reduce `ef_construction` in `_ensure_hnsw_index()`. Check `shared_buffers` in Postgres config |

---

## HITL (Human-In-The-Loop) Gates

| Symptom | Cause | Fix |
|---|---|---|
| Checkpoint event never appears on frontend | Nginx buffering SSE stream | Set `proxy_buffering off` on `/stream` location in nginx config |
| `Approve` returns `404 No pending action` | Checkpoint TTL expired (default 10 min) | Reduce agent timeout or increase Redis TTL on `agent:{run_id}:pending` key |
| Two approve clicks both succeed | Missing idempotency lock | Add `SET NX` on `agent:{run_id}:approving` key with 30s TTL before processing approval |
| Action type mismatch on approve | Tampered or wrong action_type in approve body | Compare `state["pending_action"]["type"]` with approved body's `action_type` |
| Agent stuck in `awaiting_approval` forever | Frontend disconnected, user didn't see checkpoint | Check agent run status via `GET /agents/{run_id}` API. Show stale-pending runs in UI dashboard |

---

## LLM Gateway

| Symptom | Cause | Fix |
|---|---|---|
| `No AI model configured` | User hasn't added API key in Settings | Go to Settings → AI Models, select provider, paste API key |
| `OpenAI rate limit exceeded` | Too many concurrent agent runs per user | `AGENT_MAX_CONCURRENT_PER_USER=2` should prevent this. Check for runaway retry loops |
| Extended thinking ignored | User's provider is not Anthropic | `extended_thinking` only works with Anthropic (Claude). Non-Anthropic providers fall back to regular inference — this is expected |
| `Unknown provider: X` | Provider not in supported list | Supported: anthropic, openai, google, ollama, nvidia_nim, openrouter, opencode |
| Token budget exceeded | User's daily budget consumed | Budget resets at midnight UTC. Increase in `user_model_settings.token_budget` or wait |

---

## Temporal & Follow-Ups

Follow-ups are `FollowupWorkflow` durable timers (`workflow.sleep`) firing at
day 5 and day 12 after `applied_at` — not a cron job or a queue entry.

| Symptom | Cause | Fix |
|---|---|---|
| Nothing ever runs — agent runs / searches / applications stuck in `queued` | No `temporal-worker` polling the task queue | `curl localhost:8000/health` — look for `"temporal": {"workers": 0}` (overall `status` reads `"degraded"`). `docker compose up -d temporal-worker` then `docker compose logs -f temporal-worker` |
| Follow-up drafts never appear | `FollowupWorkflow(id="followup/{application_id}")` was never started, or the worker isn't running | Check the Temporal UI for that workflow id. It's started by `schedule_followup_activity` right after a confirmed `submitted` application outcome |
| Follow-up sent even though recruiter replied | `_has_recruiter_replied()` not checking Gmail | Verify Gmail OAuth is connected for the user. Check `google_access_token_enc` exists in `users` table |
| `WorkflowUnavailable` / `503` starting a run or application | Temporal server unreachable from the API (`workflows/starters.py::_client()`) | Check `TEMPORAL_ADDRESS` (host) / `TEMPORAL_ADDRESS_DOCKER` (containers) and that the `temporal` service is healthy: `docker compose ps temporal` |
| Daily search / status check / maintenance not running | Schedules not registered | Every worker registers them at start-up (`ensure_schedules`) if `TEMPORAL_SCHEDULES_ENABLED=true`. Check the Temporal UI's Schedules tab for `daily-job-search`, `maintenance`, `application-status-check` (the latter only exists when `APPLY_EXECUTION_MODE=server_browser`) |
| Two follow-ups or two applications for the same job appear to race | Shouldn't happen — workflow ids (`followup/{application_id}`, `auto-apply/{user_id}/{job_application_id}`) make a duplicate start a no-op | Confirm in the Temporal UI that only one workflow execution exists per id; if not, file a bug — this is a correctness guarantee, not a config knob |

---

## Agent-Specific Issues

### JobSearchAgent
- **No results from LinkedIn**: LinkedIn blocks datacenter IPs. Use ProxyCurl or residential proxy. Or rely on JobSpy scraper (runs client-side).
- **Naukri returns blank**: Naukri requires Indian IP. Configure location to Indian city.
- **Indeed nationality filter**: Indeed redirects based on detected country. Use `country_indeed=India` in scrape call.

### ResumeAgent
- **ATS score 0**: Job description had no extractable keywords. Try a longer JD.
- **PDF generation errors**: ReportLab not installed. Run `pip install reportlab`.

### CoverLetterAgent
- **Word count way over limit**: LLM ignored instruction. The agent truncates to `word_limit * 6` chars. Try a more explicit prompt.
- **Extended thinking not used**: Only Claude models (`provider=anthropic`) support extended thinking. Others get standard inference.

### EmailAgent
- **Hunter.io fails with random domain**: Try using `domain_search` without first/last name. Extract domain from company name properly.
- **Draft shown but send button disabled**: This is correct — email send requires explicit approval. The checkpoint must be approved before any email is sent.

### FollowUpAgent
- **Auto-cancel fires but shouldn't**: `find_recruiter_reply()` searches 30 days of threads. Adjust `window_days` parameter if too aggressive.
- **Both day-5 and day-12 drafts appear back-to-back**: `FollowupWorkflow` computes each wait as `applied_at + timedelta(days=day) - workflow.now()`; if `applied_at` is missing or already more than 12 days old (e.g. a backfilled application), both waits resolve to zero and both activities run immediately one after the other.

### InterviewCoachAgent
- **Session expired after 2 hours**: Redis TTL is 7200s. Increase `setex` expiry in `interview_coach_agent_v2.py`.
- **Scores look random**: Scoring is LLM-based judgment. Results vary between providers. Anthropic tends to give more consistent scores.

### CompanyResearchAgent
- **All sections return "Not available"**: Exa API key missing or rate limited. Check `EXA_API_KEY` env var.
- **Firecrawl errors**: `FIRECRAWL_API_KEY` is optional. Company website scraping is skipped gracefully if not configured.

### SalaryAgent
- **Negotiation script suggests unrealistically high counter**: LLM is synthesizing from web data. Data may be inflated (levels.fyi entries are self-reported).
- **All percentiles are 0**: Exa returned no salary data for this role/location. Try a more specific role title.

### LinkedInAgent
- **ProxyCurl profile not loaded**: `PROXYCURL_API_KEY` not set. Agent still works — uses RAG context to optimize without current profile.
- **Keyword gaps show obvious words**: Keyword extraction is simple word-matching. Manual review recommended.

### NLSearchAgent
- **Parses wrong location/role**: LLM doesn't understand the query well. Make query more specific: "senior backend engineer Bangalore India" instead of "software job".
- **Always asks for confirmation**: This is HITL by design. Set `confirmed: true` in context for direct execution.

### AutoApplyPipeline
- **Stuck at Gate 1 forever**: Two HITL gates are mandatory. User must approve resume + cover letter before form filling begins.
- **Platform detected as "generic"**: URL pattern not matched. Add platform domain to `platform_detector.py`.
- **Form fill fails with "requires login"**: Naukri and Shine require pre-existing accounts. User must connect accounts in Settings.
