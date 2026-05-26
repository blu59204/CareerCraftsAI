# CareerCraft Bug Fixes — Bugfix Design

## Overview

This document formalizes the fix strategy for 29 confirmed bugs across the CareerCraft AI
full-stack application. The bugs span five severity tiers: Critical (server crash on startup),
High (features completely non-functional), Medium (partial functionality / bad UX), and Low
(minor inconsistencies). The fix approach is minimal and targeted — each change addresses
exactly the identified root cause without altering unrelated behavior.

The bug condition methodology is applied throughout: for every bug we define C(X) (the
condition that triggers the defect), P(result) (the desired correct behavior), and ¬C(X)
(the set of inputs that must be preserved unchanged). Fixes are validated by fix-checking
(all C(X) inputs now satisfy P) and preservation-checking (all ¬C(X) inputs produce the
same result as before).

---

## Glossary

- **Bug_Condition (C)**: A predicate over inputs that returns `true` when the defective code
  path is exercised.
- **Property (P)**: The desired correct behavior for inputs where C holds.
- **Preservation**: The guarantee that inputs where C does NOT hold produce identical results
  before and after the fix.
- **F**: The original (unfixed) function or component.
- **F'**: The fixed function or component.
- **Counterexample**: A concrete input that demonstrates the bug on unfixed code.
- **asyncio.run()**: Python stdlib call that creates a new event loop; illegal inside a
  thread that already has a running loop.
- **run_in_executor**: FastAPI/asyncio mechanism to run synchronous code in a thread pool
  without blocking the event loop.
- **selectinload**: SQLAlchemy eager-loading strategy that issues a separate SELECT for a
  relationship, avoiding lazy-load errors on closed sessions.
- **PGVector**: The correct class in `langchain-postgres==0.0.17` for pgvector operations;
  `langchain_postgres.v2` does not exist in this version.
- **BYOK**: Bring Your Own Key — users supply their own LLM API keys; keys are encrypted
  at rest with AES-256-GCM.
- **VALID_STATUSES**: The canonical set of job application statuses in `jobs.py`:
  `{"saved", "applied", "viewed", "interview", "offer", "rejected"}`.

---

## Bug Details

### Bug Condition — Critical Bugs (1.1–1.5)

**Bug 1.1 / 1.5 — Missing `ALLOWED_ORIGINS` in `Settings`**

`main.py` reads `settings.ALLOWED_ORIGINS` at startup. The `Settings` class in
`app/core/config.py` has no such field, so Pydantic raises `AttributeError` before the
server can bind to a port.

```
FUNCTION isBugCondition_AllowedOrigins(X)
  INPUT: X = FastAPI application startup event
  OUTPUT: boolean
  RETURN "ALLOWED_ORIGINS" NOT IN Settings.__fields__
    AND main.py READS settings.ALLOWED_ORIGINS
END FUNCTION
```

**Examples:**
- Starting `uvicorn app.main:app` → `AttributeError: 'Settings' object has no attribute 'ALLOWED_ORIGINS'`
- Any Docker Compose `up` → container exits immediately with code 1

---

**Bug 1.2 / 1.9 — `asyncio.run()` inside thread executor**

`sync_db.py` functions (`fetch_model_settings`, `fetch_user_full_name`,
`fetch_user_profile_text`) each call `asyncio.run()`. When an agent node is dispatched via
`loop.run_in_executor(None, agent_node, state)`, the worker thread inherits the running
event loop context, making `asyncio.run()` illegal.

```
FUNCTION isBugCondition_AsyncioRun(X)
  INPUT: X = agent node invocation context
  OUTPUT: boolean
  RETURN X.called_via_run_in_executor = true
    AND sync_db_function CALLS asyncio.run()
END FUNCTION
```

**Examples:**
- `POST /resume/optimize` → `RuntimeError: This event loop is already running`
- `POST /internal/agents/run-job-search` → same error in `fetch_model_settings`
- Any agent node that calls `fetch_user_profile_text` → same error

---

**Bug 1.3 — Missing `const metrics =` declaration in `dashboard/page.tsx`**

The metrics array literal is written as floating code between the query hooks and the
`return` statement with no variable declaration. Next.js cannot compile the file.

```
FUNCTION isBugCondition_MetricsSyntax(X)
  INPUT: X = Next.js compilation of dashboard/page.tsx
  OUTPUT: boolean
  RETURN metrics_array_literal EXISTS
    AND "const metrics =" NOT FOUND before array literal
END FUNCTION
```

**Examples:**
- `npm run build` → SyntaxError in `dashboard/page.tsx`
- Navigating to `/dashboard` in dev mode → white screen / compile error

---

**Bug 1.4 — `rag_service.py` imports from non-existent `langchain_postgres.v2`**

`rag_service.py` imports `PGEngine` from `langchain_postgres.v2.engine` and `PGVectorStore`
from `langchain_postgres.v2.vectorstores`. Neither submodule exists in
`langchain-postgres==0.0.17`. The correct API is `PGVector` from `langchain_postgres`.

```
FUNCTION isBugCondition_RagImport(X)
  INPUT: X = Python import of rag_service module
  OUTPUT: boolean
  RETURN langchain_postgres.__version__ = "0.0.17"
    AND import_path CONTAINS "langchain_postgres.v2"
END FUNCTION
```

**Examples:**
- Any RAG upload → `ImportError: cannot import name 'PGEngine' from 'langchain_postgres.v2.engine'`
- Resume optimization → same ImportError before agent node runs

### Bug Condition — High Bugs (1.6–1.12)

**Bug 1.6 — Email compose schema mismatch**

Frontend sends `{ subject, body, recipient }` to `POST /email/compose`. Backend
`ComposeRequest` expects `{ company, role, recipient_email, application_id? }`. Pydantic
rejects the request with HTTP 422.

```
FUNCTION isBugCondition_ComposeSchema(X)
  INPUT: X = POST /email/compose request body
  OUTPUT: boolean
  RETURN X.body CONTAINS "subject"
    AND X.body CONTAINS "recipient"
    AND X.body NOT CONTAINS "company"
END FUNCTION
```

**Examples:**
- User clicks "Save draft" on email page → HTTP 422 Unprocessable Entity

---

**Bug 1.7 — `.nullslast()` typo in `jobs.py`**

`list_applications` calls `.nullslast()` (no underscore). SQLAlchemy 2.0 uses
`.nulls_last()`. The method does not exist on the `desc()` expression object.

```
FUNCTION isBugCondition_NullsLast(X)
  INPUT: X = GET /jobs/applications request
  OUTPUT: boolean
  RETURN query CALLS ".nullslast()" on SQLAlchemy column expression
END FUNCTION
```

**Examples:**
- `GET /jobs/applications` → `AttributeError: 'desc' object has no attribute 'nullslast'`

---

**Bug 1.8 — `GmailMCPClient` crashes without OAuth credentials**

`GmailToolkit()` in `gmail_service.py` raises an exception when Google OAuth credentials
are absent. `_get_toolkit()` has no try/except, so the exception propagates to the caller.

```
FUNCTION isBugCondition_GmailOAuth(X)
  INPUT: X = GmailMCPClient instantiation or method call
  OUTPUT: boolean
  RETURN google_oauth_credentials_absent = true
    AND GmailToolkit() NOT wrapped in try/except
END FUNCTION
```

**Examples:**
- Email agent invoked without OAuth → unhandled exception in `_get_toolkit()`
- `POST /email/approve/{run_id}` → crash before `send_message` is called

---

**Bug 1.10 — Lazy `user.model_settings` on closed session**

`_get_manager()` in `memory/routes.py` accesses `user.model_settings` (a SQLAlchemy
relationship). `get_current_user` in `deps.py` does not eagerly load this relationship,
so accessing it after the session closes raises `MissingGreenlet` or `DetachedInstanceError`.

```
FUNCTION isBugCondition_LazyLoad(X)
  INPUT: X = memory endpoint request
  OUTPUT: boolean
  RETURN get_current_user DOES NOT use selectinload(User.model_settings)
    AND _get_manager() ACCESSES user.model_settings
END FUNCTION
```

**Examples:**
- `GET /api/memory/preferences` → `MissingGreenlet: greenlet_spawn has not been called`

---

**Bug 1.11 — Duplicate `AgentStatusStream` for same run**

`agents/page.tsx` mounts `AgentStatusStream` in the main panel when `activeRunId` is set,
AND again in the sidebar for `awaitingRun`. When `awaitingRun.id === activeRunId`, two SSE
connections open for the same run, causing duplicate events and double approval modals.

```
FUNCTION isBugCondition_DuplicateSSE(X)
  INPUT: X = agent run state where run transitions to awaiting_approval
  OUTPUT: boolean
  RETURN awaitingRun.id = activeRunId
    AND AgentStatusStream mounted TWICE for same runId
END FUNCTION
```

**Examples:**
- User starts a run → run reaches `awaiting_approval` → two approval modals appear

---

**Bug 1.12 — `GET /interview-prep/videos` returns 500 when `YOUTUBE_API_KEY` is empty**

`youtube_service.py` does not guard against an absent API key. When `YOUTUBE_API_KEY` is
empty, the YouTube API call raises an unhandled exception, returning HTTP 500.

```
FUNCTION isBugCondition_YouTubeKey(X)
  INPUT: X = GET /interview-prep/videos request
  OUTPUT: boolean
  RETURN settings.YOUTUBE_API_KEY = "" OR settings.YOUTUBE_API_KEY IS NULL
    AND youtube_service DOES NOT check key before calling API
END FUNCTION
```

**Examples:**
- `GET /interview-prep/videos` with no key set → HTTP 500 Internal Server Error

### Bug Condition — Medium Bugs (1.13–1.23)

**Bug 1.13 — Hardcoded ATS score on dashboard**

`dashboard/page.tsx` passes `atsScore={78}` and `keywordCoverage={64}` as static literals
to `ResumeScoreCard`. The real values are available from `GET /rag/documents?doc_type=resume`.

**Bug 1.14 — Agents page shows `"—"` for active model**

`GET /users/me` does not return an `active_model` field. The page reads
`userMe?.active_model` which is always `undefined`. The active model must be fetched from
`GET /users/me/models` and the entry with `is_active === true` selected.

**Bug 1.15 — Email page shows hardcoded "Gmail Connected"**

The left sidebar unconditionally renders a green "Gmail Connected" badge with a hardcoded
email address, regardless of whether the user has connected Gmail OAuth.

**Bug 1.16 — Password change form is a no-op**

The "Update password" button in `settings/account/page.tsx` validates fields locally and
calls `toast.success("Password updated")` without making any API call. The password is
never actually changed.

**Bug 1.17 — Delete account button is a no-op**

The "Delete my account" button has no `onClick` handler that calls an API. There is no
confirmation dialog and no account deletion occurs.

**Bug 1.18 — Connected accounts shows hardcoded state**

Google and GitHub are shown as "Connected" with green badges unconditionally. The actual
OAuth connection state from the Supabase session is never checked.

**Bug 1.19 — Sync Redis in async context (`followup_agent.py`)**

`schedule_followups` uses `redis.Redis` (synchronous). When called from the async
`run_followup` endpoint in `internal.py`, all Redis operations block the event loop.

**Bug 1.20 — `_psycopg_url()` may silently fail**

`_psycopg_url()` in `rag_service.py` replaces `+asyncpg` with `+psycopg`. If
`DATABASE_URL` does not contain `+asyncpg`, the replacement is a no-op and the URL may
be passed to psycopg3 with an incompatible driver prefix, causing a silent connection
failure.

**Bug 1.21 — Jobs page filters don't filter API results**

`jobs/page.tsx` maintains `activeFilters` in local state but the `useQuery` for
`/jobs/applications` always fetches with `?status=saved` and never passes the active
filter chips as query parameters.

**Bug 1.22 — `ApplicationKanban` stage names may not match backend**

Frontend Kanban column keys must exactly match `VALID_STATUSES` in `jobs.py`:
`{"saved", "applied", "viewed", "interview", "offer", "rejected"}`. Any mismatch causes
cards to appear in the wrong column or not at all.

**Bug 1.23 — Invalid default Anthropic model in onboarding**

`MODEL_DEFAULTS["anthropic"]` is `"claude-sonnet-4-6"` in `onboarding/page.tsx`. This
model identifier does not exist in the Anthropic API. The correct identifier is
`"claude-3-5-sonnet-20241022"` (or `"claude-sonnet-4-5"` for the newer generation).

### Bug Condition — Low Bugs (1.24–1.29)

**Bug 1.24 — Double secret verification in `internal.py`**

`run_job_search` and `run_followup` both declare `x_internal_secret: str = Header(...)` as
a parameter AND call `_verify_secret(x_internal_secret)` explicitly inside the handler
body. The secret is verified twice — once by the explicit call and once implicitly because
FastAPI would also call it if it were a `Depends`. The current pattern is redundant and
inconsistent.

**Bug 1.25 — Cover letter uses email task type**

`resume/page.tsx` calls `POST /agents/run` with `task_type: "email"` to generate a cover
letter. The email agent requires Gmail OAuth credentials and is not designed for cover
letter generation. The correct task type is `"resume_optimize"` with a `mode: "cover_letter"`
context flag.

**Bug 1.26 — LinkedIn page reads `created_at` instead of `started_at`**

`linkedin/page.tsx` defines `AgentRun` with a `created_at` field and reads
`lastRun.created_at` for the "Last analysis" banner. The backend `AgentRunResponse`
returns `started_at`, not `created_at`, so the timestamp is always `undefined`.

**Bug 1.27 — Agents page timestamp field mismatch**

`agents/page.tsx` defines `AgentRun` with `started_at` (already corrected in the
interface), but the backend `AgentRunResponse` must be verified to return `started_at`
consistently. The dashboard `page.tsx` still reads `run.created_at` in the recent runs
section.

**Bug 1.28 — `google-api-python-client` missing from `requirements.txt`**

`youtube_service.py` imports `googleapiclient` from `google-api-python-client`. This
package is not listed in `requirements.txt`, so it may be absent in a clean install.

**Bug 1.29 — `MemoryManager.initialize()` never called**

`_get_manager()` constructs a `MemoryManager` but never calls `await manager.initialize()`.
The `initialize()` method creates the database connection pool. Without it, all memory
operations silently fail or return empty results.

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- All existing authenticated API endpoints not listed in this spec SHALL continue to return
  the same HTTP status codes and response schemas as before.
- Resume upload, chunking, embedding, and ATS scoring SHALL continue to work end-to-end
  once the `rag_service.py` import is corrected.
- The human-in-the-loop gate SHALL NOT be bypassed — no email is sent and no application
  is submitted without explicit user approval via the `/approve` endpoint.
- API keys SHALL continue to be encrypted at rest with AES-256-GCM; no fix shall log or
  return plaintext key values.
- All protected endpoints SHALL continue to return HTTP 401 for requests without a valid
  Supabase JWT.
- The rate limiter SHALL continue to return HTTP 429 when the threshold is exceeded.
- `PATCH /jobs/applications/{id}/status` SHALL continue to update application status and
  return the updated record.
- `POST /jobs/search` SHALL continue to enqueue a BullMQ job search task and return a
  `queue_job_id`.
- The resume page SHALL continue to poll for ATS score updates every 3 seconds while
  `ats_score` is null.
- The Kanban board SHALL continue to allow drag-and-drop stage changes via
  `PATCH /jobs/applications/{id}/status`.
- All memory endpoints SHALL continue to scope operations to the authenticated user's ID.

**Scope of Changes:**
All inputs that do NOT trigger the identified bug conditions are completely unaffected by
these fixes. This includes:
- Requests to endpoints not modified by any fix
- Existing test suite (46 tests) — all must continue to pass
- Docker Compose startup and service health checks
- Nginx routing and `/internal/*` blocking

---

## Hypothesized Root Cause

### Critical Bugs

**1.1 / 1.5 — `ALLOWED_ORIGINS` missing from `Settings`**
Root cause: `config.py` was never updated when `main.py` added CORS middleware that reads
`settings.ALLOWED_ORIGINS`. The field was added to the middleware call but omitted from
the Pydantic `Settings` class. Fix: add `ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001"` to `Settings`.

**1.2 / 1.9 — `asyncio.run()` inside executor thread**
Root cause: `sync_db.py` was written to be called from synchronous contexts, but agent
nodes are dispatched via `run_in_executor` from an async FastAPI handler. The main event
loop is already running in the calling thread, making `asyncio.run()` illegal. Fix: replace
`asyncio.run(_fetch())` with `asyncio.run_coroutine_threadsafe(_fetch(), _main_loop).result()`
where `_main_loop` is captured at module import time via `asyncio.get_event_loop()`, OR
rewrite `sync_db.py` to use a dedicated synchronous SQLAlchemy engine (not async) so no
event loop is needed at all. The synchronous engine approach is simpler and more robust.

**1.3 — Missing `const metrics =` declaration**
Root cause: A refactor moved the metrics array out of the `return` block but forgot to
add the `const` declaration. The array literal is syntactically valid JavaScript but
semantically invalid as a statement. Fix: add `const metrics = [` before the array.

**1.4 — `langchain_postgres.v2` import**
Root cause: `rag_service.py` was written targeting a future/unreleased API of
`langchain-postgres`. The installed version (0.0.17) exposes `PGVector` directly from
`langchain_postgres`, not a `v2` submodule. Fix: rewrite `_get_pg_engine`,
`get_vector_store`, `ingest_document`, and `retrieve` to use `PGVector` with the standard
constructor API (`connection_string`, `collection_name`, `embedding`).

### High Bugs

**1.6 — Email compose schema mismatch**
Root cause: Frontend `handleSaveDraft` was written to send a simplified `{ subject, body, recipient }` payload, but the backend `ComposeRequest` schema was designed for the agent workflow and expects `{ company, role, recipient_email }`. The two were never aligned. Fix: update the frontend to send `{ company, role, recipient_email }` matching the backend schema, deriving `company` and `role` from the selected draft.

**1.7 — `.nullslast()` typo**
Root cause: SQLAlchemy 1.x used `.nullsfirst()` / `.nullslast()` (no underscore). SQLAlchemy 2.0 renamed these to `.nulls_first()` / `.nulls_last()`. The code was not updated during the SQLAlchemy 2.0 migration. Fix: one-character change.

**1.8 — `GmailMCPClient` crashes without OAuth**
Root cause: `_get_toolkit()` calls `GmailToolkit()` which reads Google OAuth credentials from the environment. When credentials are absent, it raises immediately. The method has no error handling. Fix: wrap `GmailToolkit()` instantiation in try/except; return empty list / empty dict from `search_threads` and `get_thread` on failure; raise a clear `HTTPException` from `send_message` since sending without credentials is a hard error.

**1.10 — Lazy `user.model_settings` on closed session**
Root cause: `get_current_user` in `deps.py` queries `User` without `selectinload(User.model_settings)`. SQLAlchemy defers loading the relationship until it is accessed. By the time `_get_manager()` accesses `user.model_settings`, the session from `get_current_user` has been closed. Fix: add `options(selectinload(User.model_settings))` to the `select(User)` query in `deps.py`.

**1.11 — Duplicate `AgentStatusStream`**
Root cause: The sidebar always renders `AgentStatusStream` for `awaitingRun` regardless of whether `awaitingRun.id === activeRunId`. When a run the user just started reaches `awaiting_approval`, both the main panel stream (keyed on `activeRunId`) and the sidebar stream (keyed on `awaitingRun.id`) are mounted for the same run ID. Fix: only render the sidebar `AgentStatusStream` when `awaitingRun.id !== activeRunId`.

**1.12 — YouTube 500 on missing key**
Root cause: `youtube_service.py` unconditionally calls the YouTube Data API without checking whether `YOUTUBE_API_KEY` is set. Fix: add an early return of `[]` when the key is empty.

### Medium Bugs

**1.13** — Dashboard never fetches ATS data; hardcoded literals were placeholders never replaced.
**1.14** — `GET /users/me` response schema does not include `active_model`; page never queries `/users/me/models`.
**1.15** — Gmail connection status was hardcoded as a UI placeholder; never wired to actual OAuth state.
**1.16** — Password change handler was stubbed with a fake success toast; the Supabase Auth `updateUser` call was never added.
**1.17** — Delete account button was a UI placeholder with no handler.
**1.18** — Connected accounts section was hardcoded; never reads Supabase session provider tokens.
**1.19** — `followup_agent.py` uses synchronous `redis.Redis`; the async context was not considered when the module was written.
**1.20** — `_psycopg_url()` assumes `DATABASE_URL` always contains `+asyncpg`; no validation added.
**1.21** — Filter chips update local state only; the `useQuery` key never includes filter params.
**1.22** — Kanban column keys need verification against `VALID_STATUSES`.
**1.23** — `claude-sonnet-4-6` was a speculative model name used as a placeholder; the correct identifier is `claude-3-5-sonnet-20241022`.

### Low Bugs

**1.24** — Double verification is a copy-paste artifact from an earlier pattern where `_verify_secret` was called manually before `Depends` was added.
**1.25** — Cover letter generation reused the email agent as a shortcut; a dedicated task type was never wired up.
**1.26 / 1.27** — `created_at` vs `started_at` field name mismatch introduced during a schema rename; not all frontend files were updated.
**1.28** — `google-api-python-client` was installed in the dev environment but never added to `requirements.txt`.
**1.29** — `MemoryManager.initialize()` was added as an async setup step but the call was omitted from `_get_manager()`.

---

## Correctness Properties

Property 1: Bug Condition — Server Starts Without AttributeError

_For any_ FastAPI startup event where `settings.ALLOWED_ORIGINS` is read, the fixed
`Settings` class SHALL provide the field (with a sensible default), so the server starts
without `AttributeError` and the CORS middleware is configured correctly.

**Validates: Requirements 2.5**

---

Property 2: Bug Condition — Agent Nodes Complete Without RuntimeError

_For any_ agent node invocation dispatched via `run_in_executor` where `sync_db.py`
functions are called, the fixed implementation SHALL execute database queries without
calling `asyncio.run()` inside the executor thread, so no `RuntimeError: This event loop
is already running` is raised and the agent node returns a valid status.

**Validates: Requirements 2.2, 2.9**

---

Property 3: Bug Condition — Dashboard Page Compiles and Renders

_For any_ Next.js compilation of `dashboard/page.tsx`, the fixed file SHALL compile
without syntax errors and the `metrics` array SHALL be properly declared as
`const metrics = [...]`, so the dashboard renders without a white screen.

**Validates: Requirements 2.3**

---

Property 4: Bug Condition — RAG Service Imports Successfully

_For any_ import of `rag_service.py` with `langchain-postgres==0.0.17`, the fixed module
SHALL import `PGVector` from `langchain_postgres` (not from the non-existent
`langchain_postgres.v2`), so all RAG, document upload, and vector store operations
succeed without `ImportError`.

**Validates: Requirements 2.4**

---

Property 5: Bug Condition — Email Compose Accepts Frontend Payload

_For any_ `POST /email/compose` request sent by the frontend with `{ subject, body, recipient }`,
the fixed code (either updated frontend payload or updated backend schema) SHALL return
HTTP 200 instead of HTTP 422, so draft saving works end-to-end.

**Validates: Requirements 2.6**

---

Property 6: Bug Condition — Jobs List Returns Without AttributeError

_For any_ `GET /jobs/applications` request, the fixed query SHALL call `.nulls_last()`
(with underscore) and return HTTP 200 with the application list, without raising
`AttributeError`.

**Validates: Requirements 2.7**

---

Property 7: Bug Condition — Gmail Failures Are Handled Gracefully

_For any_ invocation of `GmailMCPClient` methods when Google OAuth credentials are absent,
the fixed implementation SHALL catch the exception and return an empty list (for read
operations) or raise a clear `HTTPException` (for send operations), without propagating
an unhandled exception to the caller.

**Validates: Requirements 2.8**

---

Property 8: Bug Condition — Memory Endpoints Load `model_settings` Eagerly

_For any_ memory endpoint request, the fixed `get_current_user` SHALL eagerly load
`User.model_settings` via `selectinload`, so `_get_manager()` can access the relationship
without raising `MissingGreenlet` or `DetachedInstanceError`.

**Validates: Requirements 2.10**

---

Property 9: Bug Condition — Exactly One SSE Stream Per Run

_For any_ agent run that transitions to `awaiting_approval`, the fixed `agents/page.tsx`
SHALL mount exactly one `AgentStatusStream` component for that run ID, preventing
duplicate SSE connections and duplicate approval modals.

**Validates: Requirements 2.11**

---

Property 10: Bug Condition — Interview Prep Videos Returns Empty List on Missing Key

_For any_ `GET /interview-prep/videos` request when `YOUTUBE_API_KEY` is empty or unset,
the fixed `youtube_service.py` SHALL return `[]` with HTTP 200 instead of raising an
unhandled exception.

**Validates: Requirements 2.12**

---

Property 11: Preservation — All Non-Buggy Inputs Produce Identical Results

_For any_ input where none of the bug conditions above hold (i.e., the request does not
exercise any of the 29 defective code paths), the fixed codebase SHALL produce exactly
the same response as the original codebase, preserving all existing correct behavior
including authentication, rate limiting, encryption, human-in-the-loop gates, and all
other API contracts.

**Validates: Requirements 3.1–3.15**

---

## Fix Implementation

### Changes Required

#### Fix 1.1 / 1.5 — Add `ALLOWED_ORIGINS` to `Settings`

**File:** `backend/app/core/config.py`

**Specific Changes:**
1. Add `ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001"` to the
   `Settings` class body, after `FRONTEND_URL`.
2. No changes to `main.py` — it already reads `settings.ALLOWED_ORIGINS` correctly.

---

#### Fix 1.2 / 1.9 — Replace async engine in `sync_db.py` with synchronous engine

**File:** `backend/app/core/sync_db.py`

**Specific Changes:**
1. Replace `create_async_engine` / `async_sessionmaker` / `AsyncSession` with
   `create_engine` / `sessionmaker` / `Session` (synchronous SQLAlchemy).
2. Replace the `async def _fetch()` inner functions with synchronous `def _fetch()` bodies
   using `with factory() as db:` and synchronous `db.execute(...)`.
3. Remove all `asyncio.run()` calls — the functions become fully synchronous.
4. Update `DATABASE_URL` for the sync engine: replace `+asyncpg` with `+psycopg` (psycopg3
   sync driver, already in `requirements.txt`).
5. Keep the `threading.Lock` singleton pattern to avoid connection pool exhaustion.

---

#### Fix 1.3 — Add `const metrics =` declaration in `dashboard/page.tsx`

**File:** `frontend/src/app/(app)/dashboard/page.tsx`

**Specific Changes:**
1. Add `const metrics = [` immediately before the array literal that starts with
   `{ label: "Applications", ...`.
2. Add the closing `];` after the last element of the array.

---

#### Fix 1.4 — Rewrite `rag_service.py` to use `PGVector`

**File:** `backend/app/services/rag_service.py`

**Specific Changes:**
1. Remove `_get_pg_engine` function and its `lru_cache` decorator entirely.
2. Remove imports of `PGEngine` and `PGVectorStore` from `langchain_postgres.v2.*`.
3. Add `from langchain_postgres import PGVector` import.
4. Rewrite `get_vector_store` to use `PGVector(connection_string=_psycopg_url(), collection_name=table, embedding=embeddings)`.
5. Rewrite `ingest_document` to call `store.add_documents(docs)` (same as before, API is compatible).
6. Rewrite `retrieve` to call `store.similarity_search(query, k=k)` (same as before).
7. Keep `_psycopg_url()`, `collection_name()`, `chunk_text()`, `extract_text()`, and
   `get_embedding_model()` unchanged.

---

#### Fix 1.5 — (covered by Fix 1.1 above)

---

#### Fix 1.6 — Align email compose frontend payload with backend schema

**File:** `frontend/src/app/(app)/email/page.tsx`

**Specific Changes:**
1. In `handleSaveDraft`, change the `apiClient.post("/email/compose", ...)` payload from
   `{ subject, body, recipient }` to `{ company: selected?.company ?? "Unknown", role: selected?.subject ?? "Role", recipient_email: ... }`.
2. The `body` field is not part of `ComposeRequest` — it is generated by the agent. Remove
   it from the compose payload.

---

#### Fix 1.7 — Fix `.nullslast()` typo in `jobs.py`

**File:** `backend/app/api/v1/jobs.py`

**Specific Changes:**
1. Change `.nullslast()` to `.nulls_last()` on line with `JobApplication.applied_at.desc().nullslast()`.

---

#### Fix 1.8 — Graceful fallback in `GmailMCPClient`

**File:** `backend/app/services/gmail_service.py`

**Specific Changes:**
1. Wrap `GmailToolkit()` in `_get_toolkit()` with try/except; on exception, log a warning
   and set `self._toolkit = None`, then return `None`.
2. In `search_threads` and `get_thread`, check if `_get_toolkit()` returns `None` and
   return `[]` / `{}` respectively.
3. In `send_message`, if `_get_toolkit()` returns `None`, raise
   `HTTPException(status_code=503, detail="Gmail not connected — connect OAuth in Settings")`.

---

#### Fix 1.10 — Eager-load `model_settings` in `deps.py`

**File:** `backend/app/api/v1/deps.py`

**Specific Changes:**
1. Add `from sqlalchemy.orm import selectinload` import.
2. In `get_current_user`, change `select(User).where(User.supabase_uid == supabase_uid)`
   to `select(User).options(selectinload(User.model_settings)).where(User.supabase_uid == supabase_uid)`.
3. Apply the same `selectinload` to the fallback `select(User).where(User.email == email)` query.
4. Apply the same `selectinload` to the final re-fetch after `INSERT ... ON CONFLICT DO NOTHING`.

---

#### Fix 1.11 — Prevent duplicate `AgentStatusStream`

**File:** `frontend/src/app/(app)/agents/page.tsx`

**Specific Changes:**
1. Change the sidebar `AgentStatusStream` render condition from `{awaitingRun && (...)}` to
   `{awaitingRun && awaitingRun.id !== activeRunId && (...)}`.

---

#### Fix 1.12 — Guard against missing `YOUTUBE_API_KEY`

**File:** `backend/app/services/youtube_service.py` (and/or `backend/app/api/v1/interview_prep.py`)

**Specific Changes:**
1. At the top of the YouTube search function, add:
   `if not settings.YOUTUBE_API_KEY: return []`
2. This prevents the API call and returns an empty list gracefully.

---

#### Fix 1.13 — Fetch real ATS data on dashboard

**File:** `frontend/src/app/(app)/dashboard/page.tsx`

**Specific Changes:**
1. Add a `useQuery` for `GET /rag/documents?doc_type=resume` to fetch resume documents.
2. Extract `ats_score` and `keyword_score` from the primary document's `ats_data`.
3. Pass the real values to `ResumeScoreCard` instead of the hardcoded `78` and `64`.
4. Pass `missingKeywords` from `ats_data.missing_keywords` instead of the hardcoded array.

---

#### Fix 1.14 — Fetch active model on agents page

**File:** `frontend/src/app/(app)/agents/page.tsx`

**Specific Changes:**
1. Add a `useQuery` for `GET /users/me/models` to fetch model settings.
2. Find the entry where `is_active === true`.
3. Display `activeModel?.model_name ?? "—"` in the context sidebar instead of
   `userMe?.active_model ?? "—"`.

---

#### Fix 1.15 — Dynamic Gmail connection status on email page

**File:** `frontend/src/app/(app)/email/page.tsx`

**Specific Changes:**
1. Import the Supabase client and read the current session's `provider_token`.
2. Derive `isGmailConnected = !!session?.provider_token && session?.user?.app_metadata?.provider === "google"`.
3. Replace the hardcoded "Gmail Connected" badge with a conditional: show "Connected" with
   the user's email when `isGmailConnected`, otherwise show "Not connected" with a link to
   Settings → Account → Connected accounts.

---

#### Fix 1.16 — Wire password change to Supabase Auth

**File:** `frontend/src/app/(app)/settings/account/page.tsx`

**Specific Changes:**
1. Import `createClient` from `@supabase/ssr` (or use the existing Supabase client).
2. In the "Update password" `onClick` handler, after local validation, call
   `supabase.auth.updateUser({ password: newPwd })`.
3. Show `toast.success` only on success; show `toast.error` on failure with the error message.

---

#### Fix 1.17 — Implement delete account with confirmation

**File:** `frontend/src/app/(app)/settings/account/page.tsx`

**Specific Changes:**
1. Add a confirmation dialog (using a `useState` boolean + a modal or `window.confirm` as
   a minimal approach) before proceeding.
2. On confirmation, call `DELETE /users/me` via `apiClient.delete("/users/me")`.
3. On success, call `supabase.auth.signOut()` and redirect to `/`.
4. Show `toast.error` on failure.

---

#### Fix 1.18 — Dynamic connected accounts state

**File:** `frontend/src/app/(app)/settings/account/page.tsx`

**Specific Changes:**
1. Read the Supabase session's `user.identities` array to determine which OAuth providers
   are connected.
2. Show "Connected" badge for Google only when `identities` contains an entry with
   `provider === "google"`.
3. Show "Connected" badge for GitHub only when `identities` contains an entry with
   `provider === "github"`.
4. Show "Connect" button for providers not in `identities`.

---

#### Fix 1.19 — Convert `followup_agent.py` to async Redis

**File:** `backend/app/agents/followup_agent.py`

**Specific Changes:**
1. Replace `import redis` with `import redis.asyncio as aioredis`.
2. Change `_redis_client: redis.Redis | None` to `_redis_client: aioredis.Redis | None`.
3. Change `_get_redis()` to `async def _get_redis()` using `aioredis.from_url(...)`.
4. Change `_enqueue_followup` to `async def _enqueue_followup` and `await _get_redis()`.
5. Change `schedule_followups` to `async def schedule_followups` and `await` all Redis calls.
6. Update the caller in `internal.py` to `await schedule_followups(...)`.

---

#### Fix 1.20 — Validate `_psycopg_url()` output

**File:** `backend/app/services/rag_service.py`

**Specific Changes:**
1. After the `url.replace("+asyncpg", "+psycopg")` call, add a check:
   `if "+psycopg" not in result and "postgresql" in result: logger.warning("DATABASE_URL may not use psycopg driver: %s", result[:50])`.
2. Optionally raise a `ValueError` in strict mode to surface misconfiguration early.

---

#### Fix 1.21 — Pass active filters as query params to jobs API

**File:** `frontend/src/app/(app)/jobs/page.tsx`

**Specific Changes:**
1. Change the `useQuery` key from `["jobs-saved"]` to `["jobs-saved", Array.from(activeFilters).sort().join(",")]`.
2. In the `queryFn`, map active filter chips to API query parameters:
   - `"Remote"` → `work_mode=remote`
   - `"Full-time"` → `job_type=full-time`
   - `"Entry-level"` → `experience_level=entry`
   - Location chips → `location=<city>`
3. Append these as query string parameters to `GET /jobs/applications`.
4. The backend `list_applications` endpoint may need corresponding optional query params
   added (`work_mode`, `job_type`, `experience_level`, `location`) — add them to `jobs.py`
   with appropriate filtering logic.

---

#### Fix 1.22 — Verify `ApplicationKanban` stage names

**File:** Frontend Kanban component (wherever `ApplicationKanban` is defined)

**Specific Changes:**
1. Audit the Kanban column key definitions and ensure they exactly match
   `VALID_STATUSES`: `"saved"`, `"applied"`, `"viewed"`, `"interview"`, `"offer"`, `"rejected"`.
2. Fix any mismatches (e.g., `"Saved"` → `"saved"`, `"Interview"` → `"interview"`).

---

#### Fix 1.23 — Fix default Anthropic model in onboarding

**File:** `frontend/src/app/(app)/onboarding/page.tsx`

**Specific Changes:**
1. Change `MODEL_DEFAULTS["anthropic"]` from `"claude-sonnet-4-6"` to `"claude-3-5-sonnet-20241022"`.
2. Change the initial `formData.modelName` from `"claude-sonnet-4-6"` to `"claude-3-5-sonnet-20241022"`.

---

#### Fix 1.24 — Remove double secret verification in `internal.py`

**File:** `backend/app/api/internal.py`

**Specific Changes:**
1. Remove the explicit `_verify_secret(x_internal_secret)` call from inside the handler
   bodies of `run_job_search` and `run_followup`.
2. Convert `_verify_secret` to a proper FastAPI dependency by changing its signature to
   accept `x_internal_secret: str = Header(...)` and adding it as
   `Depends(_verify_secret)` in the route decorator, OR keep the current pattern of
   calling it explicitly but remove the `Header(...)` parameter duplication.
3. Simplest fix: remove the explicit call inside the body; keep the `Header` parameter
   and the explicit call but remove one of them.

---

#### Fix 1.25 — Use correct task type for cover letter generation

**File:** `frontend/src/app/(app)/resume/page.tsx`

**Specific Changes:**
1. In `generateCoverLetter`, change `task_type: "email"` to `task_type: "resume_optimize"`.
2. Add `mode: "cover_letter"` to the `context` object so the resume agent knows to
   generate a cover letter instead of a tailored resume.

---

#### Fix 1.26 — Fix `created_at` → `started_at` in `linkedin/page.tsx`

**File:** `frontend/src/app/(app)/linkedin/page.tsx`

**Specific Changes:**
1. Change the `AgentRun` interface field from `created_at: string` to `started_at: string`.
2. Update the "Last analysis" banner to read `lastRun.started_at` instead of `lastRun.created_at`.

---

#### Fix 1.27 — Fix `created_at` → `started_at` in `dashboard/page.tsx`

**File:** `frontend/src/app/(app)/dashboard/page.tsx`

**Specific Changes:**
1. In the `DashboardStats.recent_agent_runs` interface, change `created_at: string | null`
   to `started_at: string | null`.
2. Update `AgentStatusCard` `startedAt` prop to read `run.started_at` instead of `run.created_at`.

---

#### Fix 1.28 — Add `google-api-python-client` to `requirements.txt`

**File:** `backend/requirements.txt`

**Specific Changes:**
1. Add `google-api-python-client>=2.100.0` to `requirements.txt`.

---

#### Fix 1.29 — Call `manager.initialize()` in `_get_manager()`

**File:** `backend/memory/routes.py`

**Specific Changes:**
1. Change `_get_manager` from a synchronous function to `async def _get_manager`.
2. After constructing `MemoryManager(...)`, add `await manager.initialize()`.
3. Update all endpoint dependencies from `_get_manager(current_user)` to
   `await _get_manager(current_user)` (or use `Depends` with an async dependency).

---

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that
demonstrate each bug on unfixed code (exploratory checking), then verify the fix works
correctly and preserves existing behavior (fix checking + preservation checking).

The existing 46-test suite (40 unit + 6 security) must continue to pass after every fix.
New tests are added for each bug to prevent regression.

---

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each bug BEFORE implementing the fix.
Confirm or refute the root cause analysis.

**Test Plan**: Run the existing test suite against unfixed code to observe failures. Write
targeted tests for each bug condition and run them on unfixed code to confirm they fail
in the expected way.

**Test Cases**:

1. **Startup crash test** (Bug 1.1/1.5): Import `app.main` and assert no `AttributeError`
   is raised. Will fail on unfixed code.
2. **Executor asyncio test** (Bug 1.2/1.9): Call `fetch_model_settings("test-user")` from
   inside a `loop.run_in_executor` context. Will raise `RuntimeError` on unfixed code.
3. **Dashboard compile test** (Bug 1.3): Run `npm run build` and assert exit code 0.
   Will fail on unfixed code.
4. **RAG import test** (Bug 1.4): `import app.services.rag_service` and assert no
   `ImportError`. Will fail on unfixed code.
5. **Jobs list test** (Bug 1.7): Call `GET /jobs/applications` and assert HTTP 200.
   Will raise `AttributeError` on unfixed code.
6. **Memory endpoint test** (Bug 1.10): Call `GET /api/memory/preferences` with a valid
   JWT and assert HTTP 200. Will raise `MissingGreenlet` on unfixed code.
7. **YouTube empty key test** (Bug 1.12): Call `GET /interview-prep/videos` with
   `YOUTUBE_API_KEY=""` and assert HTTP 200 with `[]`. Will return HTTP 500 on unfixed code.

**Expected Counterexamples**:
- `AttributeError: 'Settings' object has no attribute 'ALLOWED_ORIGINS'` (Bug 1.1/1.5)
- `RuntimeError: This event loop is already running` (Bug 1.2/1.9)
- `SyntaxError` in `dashboard/page.tsx` (Bug 1.3)
- `ImportError: cannot import name 'PGEngine' from 'langchain_postgres.v2.engine'` (Bug 1.4)
- `AttributeError: 'desc' object has no attribute 'nullslast'` (Bug 1.7)
- `MissingGreenlet` or `DetachedInstanceError` (Bug 1.10)
- HTTP 500 from `youtube_service.py` (Bug 1.12)

---

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed code produces
the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixedFunction(input)
  ASSERT expectedBehavior(result)
END FOR
```

**Test Cases by Bug:**

- **1.1/1.5**: `from app.core.config import settings; assert hasattr(settings, "ALLOWED_ORIGINS")`
- **1.2/1.9**: Call `fetch_model_settings` from executor thread; assert no exception raised
- **1.3**: `npm run build` exits 0; dashboard page renders without error
- **1.4**: `import app.services.rag_service` succeeds; `PGVector` is accessible
- **1.6**: `POST /email/compose` with `{ company, role, recipient_email }` returns HTTP 200
- **1.7**: `GET /jobs/applications` returns HTTP 200 with list
- **1.8**: `GmailMCPClient.search_threads(...)` without OAuth returns `[]` (no exception)
- **1.10**: `GET /api/memory/preferences` returns HTTP 200
- **1.11**: Only one `AgentStatusStream` mounted when `awaitingRun.id === activeRunId`
- **1.12**: `GET /interview-prep/videos` with empty key returns HTTP 200 with `[]`
- **1.23**: `MODEL_DEFAULTS["anthropic"]` equals `"claude-3-5-sonnet-20241022"`
- **1.28**: `pip install -r requirements.txt` installs `googleapiclient` successfully
- **1.29**: Memory endpoints return data after `initialize()` is called

---

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed code
produces the same result as the original code.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT originalFunction(input) = fixedFunction(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking
because it generates many test cases automatically across the input domain, catching edge
cases that manual unit tests might miss.

**Test Plan**: Run the full existing 46-test suite after each fix and assert all tests
still pass. Add property-based tests for the most critical preservation properties.

**Test Cases**:

1. **Auth preservation**: Valid JWT requests to all unmodified endpoints continue to return
   the same HTTP status and response schema.
2. **Encryption preservation**: API keys stored via `POST /users/me/models` continue to be
   encrypted at rest; plaintext keys are never returned.
3. **Human-in-the-loop preservation**: `POST /email/approve/{run_id}` continues to require
   `status === "awaiting_approval"` before sending; no fix bypasses this gate.
4. **Rate limit preservation**: Requests exceeding 60/min continue to return HTTP 429.
5. **Job status update preservation**: `PATCH /jobs/applications/{id}/status` with valid
   status continues to return the updated record.
6. **Resume polling preservation**: Resume page continues to poll every 3 seconds while
   `ats_score` is null.
7. **Kanban drag-drop preservation**: Stage changes via drag-drop continue to call
   `PATCH /jobs/applications/{id}/status` correctly.

---

### Unit Tests

- Test `Settings` class has `ALLOWED_ORIGINS` field with correct default value
- Test `fetch_model_settings` runs without error when called from a thread pool executor
- Test `list_applications` query uses `.nulls_last()` and returns HTTP 200
- Test `GmailMCPClient.search_threads` returns `[]` when OAuth credentials are absent
- Test `GmailMCPClient.send_message` raises `HTTPException(503)` when OAuth is absent
- Test `get_current_user` returns `User` with `model_settings` relationship loaded
- Test `youtube_service` returns `[]` when `YOUTUBE_API_KEY` is empty
- Test `schedule_followups` is async and uses `redis.asyncio`
- Test `_psycopg_url()` logs warning when `+asyncpg` is not in `DATABASE_URL`
- Test `MemoryManager.initialize()` is called before memory operations
- Test `MODEL_DEFAULTS["anthropic"]` is a valid Anthropic model identifier
- Test `internal.py` handlers verify secret exactly once

---

### Property-Based Tests

- Generate random `Settings` configurations and verify `ALLOWED_ORIGINS` is always present
- Generate random agent node invocations via executor and verify no `RuntimeError` is raised
- Generate random `GET /jobs/applications` requests and verify HTTP 200 is always returned
- Generate random memory endpoint requests with valid JWTs and verify user scoping is preserved
- Generate random email compose payloads matching the backend schema and verify HTTP 200
- Generate random job application status values from `VALID_STATUSES` and verify Kanban
  column assignment is correct

---

### Integration Tests

- Full server startup: `uvicorn app.main:app` starts without any exception
- Full RAG pipeline: upload resume PDF → chunk → embed → store → retrieve → assert chunks returned
- Full agent flow: start resume agent → run via executor → assert no `RuntimeError` → assert
  run status is `awaiting_approval` or `completed`
- Full memory flow: save memory → recall memory → assert same content returned, scoped to user
- Full jobs flow: `GET /jobs/applications` with filters → assert filtered results returned
- Full email flow: `POST /email/compose` with correct schema → assert run created → assert
  approval gate still required before send
- Frontend build: `npm run build` exits 0 with no TypeScript or syntax errors
- Onboarding flow: select Anthropic provider → assert `claude-3-5-sonnet-20241022` is saved
