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
| `OLLAMA_ALLOWED_HOSTS` | `localhost:11434,127.0.0.1:11434,[::1]:11434` | Comma-separated `host:port` allow-list for the **user-facing** `ollama` BYOK provider's base URL (Settings → AI Models). The server fetches this URL directly, so anything outside this list — including loopback/link-local/metadata addresses reached via a different host string — is rejected at input (CWE-918 hardening). Add your own Ollama host here if it doesn't run on localhost. |

### Session limits

| Variable | Default | Description |
|---|---|---|
| `BROWSER_USE_MAX_CONCURRENT_SESSIONS` | `4` | Max simultaneous Chromium sessions. Prevents OOM. Rule of thumb: `floor(VPS_RAM_GB * 1.5)`. 4 GB VPS → 6, 2 GB VPS → 3. |
| `BROWSER_USE_SESSION_MEM_LIMIT_MB` | `500` | Informational — actual limit set via Docker `mem_limit` in `deploy/oracle-vm/compose.yml`. |

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

The settings below describe `APPLY_EXECUTION_MODE=server_browser` (Chromium
launched directly inside the `backend` container) on a generic Docker Compose
deployment. That deployment path (root `docker-compose.yml`) was retired —
the actual production stack (`deploy/oracle-vm/compose.yml`) instead runs
browser automation through the isolated `sandbox-server` (OpenSandbox)
service, which doesn't need this container to hold Chromium's memory at all.
Kept here as reference if `server_browser` mode is ever run directly again:

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
| `AGENT_MAX_CONCURRENT_PER_USER` | `2` | Max concurrent agent runs per user. Enforced by `POST /agents/run` itself (`api/v1/agents.py`), which counts the user's `queued`/`running` `agent_runs` rows and returns `429` above this limit — not a Temporal or worker-side concurrency setting. Applications waiting in the user's own browser (extension mode) use no server capacity and are excluded from the count. |
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

## Temporal

Every agent run, job search, application and follow-up executes as a durable
Temporal workflow. `python -m app.temporal_worker` (the `temporal-worker`
service) must have at least one instance running and polling
`TEMPORAL_TASK_QUEUE`, or `GET /health` reports `status: "degraded"` and
nothing the API starts makes progress.

| Variable | Default | Description |
|---|---|---|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal server address for host-run processes. |
| `TEMPORAL_ADDRESS_DOCKER` | `temporal:7233` | Address used inside Docker Compose containers instead of `TEMPORAL_ADDRESS` (so they never resolve their own localhost). Point it at Temporal Cloud to use a managed deployment. |
| `TEMPORAL_NAMESPACE` | `default` | Temporal namespace. |
| `TEMPORAL_TASK_QUEUE` | `careercraft` | Task queue the worker polls and the API starts workflows on. |
| `TEMPORAL_WORKER_CONCURRENCY` | `4` | Max concurrent activities per worker process (`max_concurrent_activities`). Scale further by running more `temporal-worker` replicas. |
| `WORKFLOW_TASK_TIMEOUT_S` | `300` | Max duration of one agent execute/continue activity. |
| `AGENT_APPROVAL_TIMEOUT_S` | `172800` (48h) | How long a run may sit at an approval checkpoint before it expires. |
| `TEMPORAL_WORKFLOW_EXECUTION_TIMEOUT_S` | `600` | Hard execution cap for `server_browser` applications only; the extension flow waits on the user and is bounded by the `EXTENSION_TASK_*` timeouts instead. |
| `TEMPORAL_ACTIVITY_START_TO_CLOSE_TIMEOUT_S` | `120` | Upper bound for one activity attempt. |
| `TEMPORAL_ACTIVITY_HEARTBEAT_TIMEOUT_S` | `30` | Heartbeat timeout for long-running activities. |
| `TEMPORAL_ACTIVITY_HEARTBEAT_INTERVAL_S` | `5` | How often a heartbeating activity checks in. |
| `TEMPORAL_SCHEDULES_ENABLED` | `true` | Whether the worker registers the recurring Schedules at start-up. |
| `DAILY_SEARCH_INTERVAL_HOURS` | `24` | Interval of the `daily-job-search` Temporal Schedule. |
| `STATUS_CHECK_INTERVAL_HOURS` | `6` | Interval of the `application-status-check` Schedule — only registered when `APPLY_EXECUTION_MODE=server_browser`. |
| `MAINTENANCE_INTERVAL_SECONDS` | `60` | Interval of the `maintenance` Schedule (reconciles `agent_runs`, expires stale extension tasks, reaps browser sandboxes). |
| `TEMPORAL_TLS_CERT_PATH` / `TEMPORAL_TLS_KEY_PATH` / `TEMPORAL_TLS_CA_PATH` | *(empty)* | mTLS certificate paths for Temporal Cloud. Empty connects in plaintext (local dev only). |

---

## Job Applications (extension / decision engine)

| Variable | Default | Description |
|---|---|---|
| `APPLY_EXECUTION_MODE` | `extension` | `extension` — fill and submit in the user's own browser via the CareerCraft extension. `server_browser` — legacy mode: drive an isolated OpenSandbox browser server-side. |
| `EXTENSION_TASK_CLAIM_TIMEOUT_S` | `86400` (24h) | An extension task nobody claims (extension offline) expires after this long. |
| `EXTENSION_TASK_COMPLETE_TIMEOUT_S` | `7200` (2h) | Once claimed, how long the user has to review and press Submit. |
| `DECISION_ENGINE_PROVIDER` | `auto` | `auto` (Jev if `TYPESAFE_API_KEY` is set, else Laya if `LAYA_URL` is set, else heuristics), or force `jev` / `laya` / `none`. |
| `DECISION_ENGINE_TIMEOUT_S` | `5.0` | Timeout for one decision-engine HTTP call. |
| `DECISION_ENGINE_MIN_CONFIDENCE` | `0.6` | Answers below this confidence are left to the user instead of acted on. |
| `TYPESAFE_API_KEY` | *(empty)* | TypeSafe Jev API key (hosted "System One" decision model). |
| `TYPESAFE_BASE_URL` | `https://api.typesafe.ai` | Jev API base URL. |
| `TYPESAFE_MODEL` | `jev-latest` | Jev model name. |
| `LAYA_URL` | *(empty)* | Self-hosted Laya server URL (see `deploy/laya/`), e.g. `http://laya:8088`. |
| `LAYA_API_KEY` | *(empty)* | Laya API key, if the self-hosted server requires one. |
| `OPEN_SANDBOX_URL` / `OPEN_SANDBOX_API_KEY` / `OPEN_SANDBOX_CHROME_IMAGE` | *(empty)* / *(empty)* / `careercraft-browser:1` | OpenSandbox lifecycle server — `server_browser` mode only. |
| `SANDBOX_MAX_ACTIVE` | `4` | Max concurrent sandbox browsers. |
| `SANDBOX_TTL_SECONDS` | `1800` | Sandbox lifetime before it's reaped. |
| `SANDBOX_CPU` / `SANDBOX_MEMORY` | `1000m` / `1024Mi` | Per-sandbox resource limits. |
| `SANDBOX_ALLOWED_DOMAINS` | *(empty)* | Comma-separated domain allowlist for sandbox network egress. Empty fails closed. |

See [`extension/README.md`](../extension/README.md) and
[`deploy/laya/README.md`](../deploy/laya/README.md) for how the extension
and the decision engine work end to end.

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

## Nango integrations (Gmail and Drive)

Gmail and Drive are authorized through Nango, not Supabase Auth. Configure
`NANGO_ENABLED`, `NANGO_SECRET_KEY`, `NANGO_WEBHOOK_SECRET`, and the
environment-specific `NANGO_PROVIDER_CONFIG_KEYS` mapping described in
[`NANGO_INTEGRATION.md`](NANGO_INTEGRATION.md). Nango holds and refreshes
provider credentials; CareerCraft does not store provider OAuth tokens.

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
