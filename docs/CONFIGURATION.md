# Configuration Reference

All configuration is loaded from environment variables. The backend uses `pydantic-settings` (`app/core/config.py`) — values are validated at startup and the app exits with a clear error if required variables are missing.

Copy `.env.example` to `.env` and fill in values before starting.

---

## Required Variables

These must be set for the app to start.

| Variable | Example | Description |
|---|---|---|
| `APP_SECRET_KEY` | `openssl rand -hex 32` | AES-256 master key for API key encryption. 32+ bytes. |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:pass@db.xyz.supabase.co:5432/postgres` | Async PostgreSQL connection string. Must use `asyncpg` driver. |
| `SUPABASE_URL` | `https://xyz.supabase.co` | Supabase project URL. |
| `SUPABASE_SERVICE_KEY` | `eyJhbGci...` | Supabase `service_role` key. Never expose to frontend. |
| `SUPABASE_JWT_SECRET` | `your-jwt-secret` | From Supabase → Settings → API → JWT Secret. Used to verify user tokens locally. |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xyz.supabase.co` | Supabase URL exposed to Next.js client. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `eyJhbGci...` | Supabase `anon` key exposed to Next.js client. Safe to expose. |
| `REDIS_URL` | `redis://redis:6379` | Redis connection URL. Use `redis://redis:6379` when running via Docker Compose. |

---

## Application Settings

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development` or `production`. Production disables `/docs` and debug logging. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed CORS origins. In production: `https://yourdomain.com` |
| `NEXT_PUBLIC_APP_URL` | `http://localhost:3000` | Full frontend URL. Used for OAuth redirect construction. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL as seen by the browser. |

---

## External API Keys

All optional — features gracefully degrade if not set.

| Variable | Provider | Used By | Description |
|---|---|---|---|
| `HUNTER_API_KEY` | [hunter.io](https://hunter.io) | EmailAgent, LeadsAgent | Finds recruiter email addresses by domain + name. |
| `PROXYCURL_API_KEY` | [proxycurl.com](https://proxycurl.com) | LinkedInAgent | Fetches LinkedIn profile data without scraping. |
| `EXA_API_KEY` | [exa.ai](https://exa.ai) | CompanyResearchAgent, SalaryAgent, InterviewPrepAgent | Neural web search for research tasks. |
| `RESEND_API_KEY` | [resend.com](https://resend.com) | ResendService | Sends transactional emails (account notifications, not job emails). |
| `YOUTUBE_API_KEY` | [Google Cloud](https://console.cloud.google.com) | InterviewPrepAgent | Fetches interview prep videos (optional enrichment). |

---

## Browser Use (Playwright/Chromium)

Browser Use drives a real Chromium browser for job board automation (Naukri, LinkedIn, etc.).

### Controller LLM

Browser Use needs its own LLM to reason about the page.  Use a local Ollama model for cost-efficient navigation; the user's BYOK model is used as fallback.

| Variable | Default | Description |
|---|---|---|
| `BROWSER_USE_OLLAMA_MODEL` | `llama3.2` | Ollama model for browser navigation steps (cost-efficient). |
| `BROWSER_USE_OLLAMA_URL` | *(empty)* | Ollama base URL, e.g. `http://localhost:11434`. Leave empty to use user's BYOK model instead. |

### Session limits

| Variable | Default | Description |
|---|---|---|
| `BROWSER_USE_MAX_CONCURRENT_SESSIONS` | `4` | Max simultaneous Chromium sessions. Prevents OOM. Rule of thumb: `floor(VPS_RAM_GB * 1.5)`. 4 GB VPS → 6, 2 GB VPS → 3. |
| `BROWSER_USE_SESSION_MEM_LIMIT_MB` | `500` | Informational — actual limit set via Docker `mem_limit` in `docker-compose.yml`. |

### Debug screenshots

When enabled, a PNG is saved to `BROWSER_DEBUG_DIR` on every browser task failure.  Mount the `browser_debug` Docker volume to persist screenshots across restarts.

| Variable | Default | Description |
|---|---|---|
| `BROWSER_DEBUG_SCREENSHOTS` | `false` | Set `true` to save failure screenshots. Disable in production to avoid disk fill. |
| `BROWSER_DEBUG_DIR` | `/tmp/browser_debug` | Container path for failure screenshots. Maps to the `browser_debug` Docker volume. |

Inspect screenshots: `docker compose exec backend ls /tmp/browser_debug/`

### Human-like delay ranges

All values in milliseconds.  Lowering increases detection risk; raising slows runs.

| Variable | Default | Description |
|---|---|---|
| `BROWSER_DELAY_NAVIGATE_MIN_MS` | `1500` | Min pause after page navigation. |
| `BROWSER_DELAY_NAVIGATE_MAX_MS` | `3500` | Max pause after page navigation. |
| `BROWSER_DELAY_FILL_MIN_MS` | `300` | Min pause between form field fills. |
| `BROWSER_DELAY_FILL_MAX_MS` | `800` | Max pause between form field fills. |
| `BROWSER_DELAY_CLICK_MIN_MS` | `200` | Min pause before/after a button click. |
| `BROWSER_DELAY_CLICK_MAX_MS` | `600` | Max pause before/after a button click. |
| `BROWSER_DELAY_EXTRACT_MIN_MS` | `500` | Min wait after page load before extraction. |
| `BROWSER_DELAY_EXTRACT_MAX_MS` | `1500` | Max wait after page load before extraction. |

### Anti-detection trigger condition

Monitor the `phase: "captcha_detected"` SSE events emitted by `browser_control_service.py`.  If the CAPTCHA block rate exceeds **20% over any rolling 10-run window** for a given platform, route that platform's traffic through a paid proxy (Scrapfly / Browserbase).

Do **not** add proxies preemptively — they add cost and latency and are unnecessary for low-volume use.

### Docker Compose resource configuration

The `backend` service in `docker-compose.yml` sets:

```yaml
mem_limit: 2500m        # total backend container RAM (includes Chromium sessions)
shm_size: "256m"        # required — Chromium crashes without /dev/shm space
volumes:
  - browser_debug:/tmp/browser_debug
```

Tune `mem_limit` based on VPS size: 4 GB VPS → `2500m`, 8 GB VPS → `5000m`.

---

---

## Agent Settings

| Variable | Default | Description |
|---|---|---|
| `AGENT_DEFAULT_TIMEOUT_S` | `60` | Default agent run timeout. Overridden per-agent (see AGENTS.md). |
| `AGENT_MAX_CONCURRENT_PER_USER` | `2` | BullMQ worker concurrency limit per user. |
| `AGENT_THINKING_BUDGET_TOKENS` | `8000` | Extended thinking token budget for Claude. |
| `RAG_CHUNK_SIZE` | `500` | Document chunk size in tokens. |
| `RAG_CHUNK_OVERLAP` | `50` | Chunk overlap in tokens. |
| `RAG_TOP_K` | `5` | Number of chunks to retrieve per RAG query. |

---

## Rate Limiting

| Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_DEFAULT` | `60/minute` | Default rate limit for all authenticated endpoints. |
| `RATE_LIMIT_AGENT_RUN` | `10/minute` | Rate limit for `POST /agents/run`. |
| `RATE_LIMIT_UPLOAD` | `5/minute` | Rate limit for document uploads. |

---

## Worker (BullMQ)

Set in `worker/.env` or inherited from root `.env`:

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | (shared with backend) | Redis connection for BullMQ. |
| `BACKEND_INTERNAL_URL` | `http://backend:8000` | Backend URL for internal callbacks. Never public. |
| `INTERNAL_SECRET` | required | Shared secret for worker → backend internal calls. Set same value on both services. |
| `DAILY_SEARCH_CRON` | `0 8 * * *` | Cron schedule for daily job search (8am UTC). |
| `STATUS_CHECK_CRON` | `0 */6 * * *` | Cron for application status polling (every 6h). |

---

## Nginx

Nginx reads environment from the host. Set in `nginx/nginx.conf`:

| Variable | Description |
|---|---|
| `${DOMAIN}` | Your domain name. Replace with `sed -i 's/${DOMAIN}/yourdomain.com/g' nginx/nginx.conf` |

---

## Supabase Storage

| Variable | Default | Description |
|---|---|---|
| `SUPABASE_STORAGE_BUCKET` | `documents` | Bucket name for uploaded resumes and generated PDFs. Created by migration 0003. |

---

## Google OAuth (for Gmail Agent)

Set in Supabase Auth dashboard, not in `.env`. The Google OAuth client credentials are configured in Supabase → Authentication → Providers → Google.

Required Google Cloud OAuth scopes:
```
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/drive.readonly
email
profile
```

After a user signs in with Google and grants these scopes, the refresh token is stored in Supabase Auth and used by `GmailService` to call the Gmail API on the user's behalf.

---

## Development vs Production Differences

| Setting | Development | Production |
|---|---|---|
| `APP_ENV` | `development` | `production` |
| `/docs` endpoint | Enabled | Disabled |
| Debug logging | Enabled | Disabled |
| CORS origins | `localhost:3000` | `https://yourdomain.com` |
| HTTPS | Optional | Required (Nginx + Certbot) |
| Redis persistence | Not required | `appendonly yes` |
| Supabase | Any project | Dedicated project with backups enabled |

---

## .env.example

The repo includes `.env.example` with all variables and inline comments. Always copy it:

```bash
cp .env.example .env
```

Never commit `.env` — it is in `.gitignore`. Never commit real API keys in any file.
