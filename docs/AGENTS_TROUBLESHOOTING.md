# CareerCraft AI — Agent Troubleshooting Guide

Common failure modes and resolution steps for all 15 agents, Playwright browser automation, Gmail OAuth, RAG, HITL gates, and BullMQ.

---

## Browser Automation (Playwright/Chromium)

| Symptom | Cause | Fix |
|---|---|---|
| `Element not found: .jobs-apply-button` | LinkedIn UI changed CSS selectors | Screenshot on failure for debugging. Update selectors in `platform_detector.py` |
| CAPTCHA detected during form fill | LinkedIn anti-bot protection triggered | Screenshot captured. Retry with fresh browser context. Notify user via SSE `checkpoint` event — manual solve required |
| Browser context leaking between users | Missing `user_id` parameter | Each request must pass `user_id` parameter for context isolation |

---

## Gmail OAuth & Email

| Symptom | Cause | Fix |
|---|---|---|
| `Gmail not connected` | User signed in with Google but without Gmail scopes | User must disconnect Google in Settings, then reconnect and approve `gmail.send` and `gmail.readonly` scopes |
| `Token refresh failed` | Google OAuth client credentials missing or wrong | Verify `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` in Supabase Auth provider settings |
| `Insufficient Permission` (403) | User approved Google sign-in but not Gmail scopes | Prompt user to re-authenticate with full Gmail permissions |
| `Gmail API is not enabled` (403) | Gmail API not enabled in Google Cloud Console | Enable Gmail API for the project at `console.cloud.google.com/apis/library/gmail.googleapis.com` |
| Email draft generated but not sent | HITL gate — this is expected behavior | Email send only happens after user approves the checkpoint event via the ApprovalModal in the frontend |
| Hunter.io `found: False` | No email pattern found for company domain | Verify `HUNTER_API_KEY` is set. Try different name combinations. Fall back to domain search |
| Hunter.io `402 Payment Required` | Free tier exhausted (500 requests/month) | Upgrade Hunter.io plan or add a different email finding API (e.g., FindEmails, Snov.io) |

---

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

## BullMQ & Follow-Ups

| Symptom | Cause | Fix |
|---|---|---|
| Follow-up jobs never fire | Worker container not running | `docker compose up worker -d`. Verify `REDIS_URL` matches between backend and worker |
| Jobs stuck in `waiting` state | Worker concurrency exhausted | Default: 2 concurrent jobs per worker. Increase in `worker/src/index.ts` if needed |
| Follow-up sent even though recruiter replied | `_has_recruiter_replied()` not checking Gmail | Verify Gmail OAuth is connected for the user. Check `google_access_token_enc` exists in `users` table |
| `bullmq not installed` warning in dev | Python `bullmq` package missing | `pip install bullmq` (optional — dev mode runs jobs inline) |
| Daily search not running | Cron scheduler not configured | Verify `AGENT_DEFAULT_TIMEOUT_S` and `DAILY_SEARCH_CRON` env vars. Check `status-check` processor in worker |

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
- **Both day-5 and day-12 fire simultaneously**: BullMQ scheduler uses UTC. Check clock synchronization.

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
