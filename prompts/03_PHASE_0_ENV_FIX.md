# PHASE 0 — MAKE THE ENVIRONMENT GREEN (nothing else)

## Goal
Backend boots, Redis auth works, SSE stream does not crash, worker sees noeviction, /health returns all "ok".
NO feature work. NO refactoring.

## READ THESE FILES (paste them)
- .env (redact values as XXXX but keep the KEY NAMES and show whether REDIS_PASSWORD is set)
- backend/app/core/config.py
- backend/app/core/event_bus.py
- backend/app/core/redis_client.py
- backend/app/main.py
- docker-compose.dev.yml (redis service block only)
- worker/src/index.ts (connection setup only)
- worker/.env (redacted)
- Last 60 lines of backend-run.err.log and worker-run.err.log

## TASK 0.1 — Redis alignment (do this first, alone)
Decide ONE of:
  (A) Run Redis via docker: `docker compose -f docker-compose.dev.yml up -d redis`
      → then backend .env must have REDIS_PASSWORD=<same as compose default 'changeme' or your value>
      and REDIS_URL=redis://localhost:6379 (config.py injects the password automatically).
      Worker .env must build REDIS_URL with the password: redis://:changeme@localhost:6379
  (B) Local Redis without password → remove REDIS_PASSWORD from ALL .env files and start redis with
      `--maxmemory-policy noeviction`.
Output: exact .env lines to change (keys only, placeholder values), exact command to start Redis, exact verify.
VERIFY:
  redis-cli -a <pw> ping                  → PONG
  redis-cli -a <pw> CONFIG GET maxmemory-policy → noeviction
  Start backend, curl http://localhost:8000/health → {"status":"ok","redis":"ok",...}
  Start a run, curl -N http://localhost:8000/api/v1/agents/<id>/stream -H "Authorization: Bearer <jwt>"
  → no "Authentication required" in backend-run.err.log

## TASK 0.2 — event_bus.py resilience
Make stream_events() catch redis.exceptions.AuthenticationError and ConnectionError, emit ONE SSE
`error {message:"event bus unavailable"}` and close cleanly instead of raising 500. Do not change event names.
VERIFY: stop redis, hit /stream, get a clean error event, not a traceback.

## TASK 0.3 — Duplicate operation id
Two routers both register `proxy_llm_request` (backend/app/core/llm_gateway.py and
backend/app/services/llm_gateway.py). Paste both files. Decide which one main.py includes
(grep `include_router` in main.py). Keep THAT one. Move the other to `_archive/backend/app/<path>`.
If both are imported somewhere, list every importer under PLAN and update imports to the kept one.
VERIFY: start backend → no "Duplicate Operation ID" UserWarning in backend-run.err.log.
        curl http://localhost:8000/openapi.json | findstr /c:"proxy_llm_request" → appears once.

## TASK 0.4 — Worker green
Paste worker/src/index.ts, worker/src/processors/status-check.processor.ts, backend/app/api/internal.py.
Confirm: worker sends header `X-Internal-Secret` = INTERNAL_SECRET, URL = BACKEND_INTERNAL_URL (for local
dev this must be http://localhost:8000 NOT http://backend:8000). Make the processor log the HTTP status and
response body on failure (currently logs empty string).
VERIFY: cd worker; npm run build; npm run dev → no "Eviction policy" warning; trigger status-check;
        worker-run.err.log shows either success or a real HTTP error with body.

## TASK 0.5 — Health endpoint truth
Paste backend/app/main.py /health handler. Ensure it returns {"status","version","db","redis","pgvector"} where
each is "ok" or an error string, and returns HTTP 503 if any is not ok.
VERIFY: curl -i http://localhost:8000/health → 200 and all "ok".

## PHASE 0 EXIT CRITERIA (all true before Phase 1)
[ ] /health 200 all ok
[ ] SSE stream connects with no auth traceback
[ ] worker: no eviction warning, status-check completes or shows real error
[ ] no Duplicate Operation ID warning
[ ] git commit: "fix(infra): align redis auth, harden event bus, dedupe llm gateway, worker logging"
