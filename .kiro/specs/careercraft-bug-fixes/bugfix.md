# Bugfix Requirements Document

## Introduction

This document covers a comprehensive audit of 30 bugs across the CareerCraft AI full-stack application. The bugs span five severity tiers: Critical (app won't start / core features broken), High (features completely non-functional), Medium (partial functionality / bad UX), and Low (minor issues). Left unaddressed, the Critical and High bugs make the application entirely unusable — the FastAPI server crashes on startup, all agent nodes fail at runtime, the dashboard page throws a syntax error, and the RAG/vector store layer uses a non-existent API. The fixes must restore correct behavior for all affected inputs while preserving all existing behavior for unaffected inputs.

---

## Bug Analysis

### Current Behavior (Defect)

**CRITICAL — App Won't Start / Core Features Broken**

1.1 WHEN the FastAPI server starts THEN the system crashes with `ImportError` because `memory/routes.py` imports from `memory.embedder`, `memory.manager`, and `memory.models` — if any of those files are absent or contain their own broken imports, the entire application fails to start.

1.2 WHEN any agent node (`resume_agent_node`, `job_search_agent_node`, `email_agent_node`, `linkedin_agent_node`, `interview_prep_agent_node`) is invoked via `loop.run_in_executor(None, ...)` THEN the system raises `RuntimeError: This event loop is already running` because `sync_db.py`'s `fetch_model_settings()`, `fetch_user_full_name()`, and `fetch_user_profile_text()` each call `asyncio.run()`, which attempts to create a new event loop inside a thread that already has one, causing all agents to fail.

1.3 WHEN the dashboard page (`dashboard/page.tsx`) is rendered THEN the system throws a JavaScript syntax error because the `metrics` array literal is written as floating code between the query hooks and the `return` statement with no `const metrics =` declaration, preventing the page from compiling or rendering.

1.4 WHEN any document upload, RAG retrieval, resume optimization, LinkedIn agent, or interview prep feature is used THEN the system raises `ImportError: cannot import name 'PGEngine' from 'langchain_postgres.v2.engine'` because `rag_service.py` imports from `langchain_postgres.v2` which does not exist in `langchain-postgres==0.0.17`; the correct class is `PGVector` from `langchain_postgres`.

1.5 WHEN the FastAPI server starts THEN the system raises `AttributeError: 'Settings' object has no attribute 'ALLOWED_ORIGINS'` because `main.py` reads `settings.ALLOWED_ORIGINS` but the `Settings` class in `config.py` has no `ALLOWED_ORIGINS` field.

**HIGH — Features Completely Non-Functional**

1.6 WHEN the frontend calls `POST /email/compose` with `{ subject, body, recipient }` THEN the system returns HTTP 422 Unprocessable Entity because the backend `ComposeRequest` schema expects `{ company, role, recipient_email, application_id }` — the field names do not match.

1.7 WHEN `GET /jobs/applications` is called THEN the system raises `AttributeError: 'desc' object has no attribute 'nullslast'` because `jobs.py` calls `.nullslast()` (no underscore) on a SQLAlchemy column expression; the correct method is `.nulls_last()`.

1.8 WHEN the email agent or the `POST /email/approve/{run_id}` endpoint is invoked THEN the system raises an exception during `GmailMCPClient` instantiation because `GmailToolkit()` requires Google OAuth credentials that are not present, and there is no graceful fallback.

1.9 WHEN `POST /resume/optimize` is called THEN the system raises `RuntimeError: This event loop is already running` because `resume.py` calls `run_in_executor(None, resume_agent_node, state)` and `resume_agent_node` internally calls `fetch_model_settings` which calls `asyncio.run()` inside the executor thread (same root cause as Bug 1.2).

1.10 WHEN any memory endpoint (`GET /api/memory/preferences`, `/blacklist`, `/recall`, `/save`, etc.) is called THEN the system raises `MissingGreenlet` or `DetachedInstanceError` because `_get_manager()` in `memory/routes.py` accesses `user.model_settings` as a lazy-loaded relationship on a session that has already been closed.

1.11 WHEN an agent run transitions to `awaiting_approval` status THEN the system opens two simultaneous SSE connections for the same run because `agents/page.tsx` mounts `AgentStatusStream` once in the main panel (when `activeRunId` is set) and again in the sidebar (for `awaitingRun`), causing duplicate events and double approval modals.

1.12 WHEN `GET /interview-prep/videos` is called and `YOUTUBE_API_KEY` is empty or unset THEN the system returns HTTP 500 instead of an empty list because `youtube_service.py` raises an unhandled exception when the API key is absent.

**MEDIUM — Partial Functionality / Bad UX**

1.13 WHEN the dashboard page renders THEN the system displays a hardcoded ATS score of `78` in `ResumeScoreCard` regardless of the user's actual resume score, because `dashboard/page.tsx` passes `atsScore={78}` and `keywordCoverage={64}` as static literals instead of values from the fetched ATS data.

1.14 WHEN the agents page context sidebar renders THEN the system always shows `"—"` for the active model because `UserResponse` from `GET /users/me` does not include an `active_model` field, and the page does not query `/users/me/models` to find the active model.

1.15 WHEN the email page sidebar renders THEN the system unconditionally displays a green "Gmail Connected" badge with a hardcoded email address, regardless of whether the user has actually connected Gmail OAuth.

1.16 WHEN the user fills in the "Change password" form and clicks "Update password" THEN the system shows `toast.success("Password updated")` without making any API call, silently discarding the password change.

1.17 WHEN the user clicks "Delete my account" THEN the system does nothing — there is no API call and no confirmation dialog; the button is a no-op.

1.18 WHEN the account settings page renders the "Connected accounts" section THEN the system shows Google and GitHub as always "Connected" with hardcoded green badges, regardless of actual OAuth connection state.

1.19 WHEN `schedule_followups` is called from an async endpoint in `internal.py` THEN the system blocks the event loop because `followup_agent.py`'s `_get_redis()` returns a synchronous `redis.Redis` client and all Redis calls are synchronous, stalling the async request handler.

1.20 WHEN `DATABASE_URL` does not contain the `+asyncpg` driver prefix THEN the system silently passes the unchanged URL to psycopg3 in `rag_service.py`'s `_psycopg_url()`, which may cause a silent connection failure or incorrect driver selection.

1.21 WHEN the user activates filter chips (Remote, Full-time, Entry-level, etc.) on the jobs page THEN the system does not filter the displayed jobs because `jobs/page.tsx` only updates local UI state — the active filters are never passed as query parameters to `GET /jobs/applications`.

1.22 WHEN the `ApplicationKanban` component renders application cards THEN the system may display cards in the wrong column or fail to match status values if the frontend stage names do not exactly match the backend `VALID_STATUSES` set `{"saved", "applied", "viewed", "interview", "offer", "rejected"}`.

1.23 WHEN a new user completes onboarding and selects "Anthropic" as their provider THEN the system saves `claude-sonnet-4-6` as the model name, which is not a valid Anthropic model identifier, causing API errors on first agent use.

**LOW — Minor Issues**

1.24 WHEN `internal.py` processes a request THEN the system calls `_verify_secret(x_internal_secret)` both explicitly inside the handler body and as a FastAPI dependency, resulting in the secret being verified twice — an inconsistent and redundant pattern.

1.25 WHEN the user clicks "Generate Cover Letter" on the resume page THEN the system calls `POST /agents/run` with `task_type: "email"`, which requires Gmail OAuth credentials and triggers the email agent instead of a dedicated cover letter or resume agent task.

1.26 WHEN the LinkedIn page renders the "Last analysis" banner THEN the system shows `undefined` for the timestamp because `linkedin/page.tsx` reads `lastRun.created_at` but the backend `AgentRunResponse` returns `started_at`, not `created_at`.

1.27 WHEN the agents page run history renders THEN the system shows `undefined` for run timestamps because `agents/page.tsx` previously referenced `created_at` on `AgentRun` objects (same field mismatch as Bug 1.26; the interface has since been corrected to `started_at` but the backend response must be verified to match).

1.28 WHEN `YOUTUBE_API_KEY` is set and `GET /interview-prep/videos` is called THEN the system may raise `ImportError: No module named 'googleapiclient'` because `google-api-python-client` may not be listed in `requirements.txt`.

1.29 WHEN any memory endpoint is called THEN the system may silently return empty data or fail because `MemoryManager.__init__` sets up the object but `initialize()` — which creates the database connection pool — is never called in `_get_manager()` in `memory/routes.py`.

---

### Expected Behavior (Correct)

**CRITICAL**

2.1 WHEN the FastAPI server starts THEN the system SHALL import `memory/routes.py` and all its dependencies (`memory.embedder`, `memory.manager`, `memory.models`) successfully, and the server SHALL start without `ImportError`.

2.2 WHEN any agent node is invoked via `run_in_executor` THEN the system SHALL execute all synchronous database calls (`fetch_model_settings`, `fetch_user_full_name`, `fetch_user_profile_text`) without calling `asyncio.run()` inside the thread, using instead a dedicated synchronous SQLAlchemy engine or `asyncio.run_coroutine_threadsafe` with the correct event loop, so that no `RuntimeError: This event loop is already running` is raised and all agents complete successfully.

2.3 WHEN the dashboard page is rendered THEN the system SHALL compile and render without JavaScript syntax errors, with the `metrics` array properly declared as `const metrics = [...]` inside the component function body.

2.4 WHEN any RAG, document upload, or vector store operation is performed THEN the system SHALL use the correct `PGVector` class from `langchain_postgres` (not from the non-existent `langchain_postgres.v2` submodule), and all document ingestion and retrieval SHALL succeed.

2.5 WHEN the FastAPI server starts THEN the system SHALL read `ALLOWED_ORIGINS` from the environment via the `Settings` class in `config.py` (with a sensible default), and the server SHALL start without `AttributeError`.

**HIGH**

2.6 WHEN the frontend calls `POST /email/compose` with `{ subject, body, recipient }` THEN the system SHALL accept the request with HTTP 200 (or the frontend SHALL be updated to send `{ company, role, recipient_email }` matching the backend schema), so that draft saving no longer returns HTTP 422.

2.7 WHEN `GET /jobs/applications` is called THEN the system SHALL order results using `.nulls_last()` (with underscore) and return HTTP 200 with the application list, without raising `AttributeError`.

2.8 WHEN the email agent or email approval endpoint is invoked THEN the system SHALL handle missing Gmail OAuth credentials gracefully — either by returning a clear error message to the user or by skipping Gmail thread lookup — without raising an unhandled exception.

2.9 WHEN `POST /resume/optimize` is called THEN the system SHALL run `resume_agent_node` without triggering `RuntimeError: This event loop is already running`, and resume optimization SHALL complete successfully.

2.10 WHEN any memory endpoint is called THEN the system SHALL eagerly load `user.model_settings` in `get_current_user` (via `selectinload`) so that `_get_manager()` can access the relationship on a live session without raising `MissingGreenlet` or `DetachedInstanceError`.

2.11 WHEN an agent run transitions to `awaiting_approval` THEN the system SHALL render exactly one `AgentStatusStream` component for that run, preventing duplicate SSE connections and duplicate approval modals.

2.12 WHEN `GET /interview-prep/videos` is called and `YOUTUBE_API_KEY` is empty or unset THEN the system SHALL return an empty list (`[]`) with HTTP 200 instead of raising an unhandled exception and returning HTTP 500.

**MEDIUM**

2.13 WHEN the dashboard page renders THEN the system SHALL pass the real ATS score and keyword coverage values fetched from the API to `ResumeScoreCard`, so users see their actual resume score instead of the hardcoded value of 78.

2.14 WHEN the agents page context sidebar renders THEN the system SHALL display the user's active model name by querying `/users/me/models` and finding the model where `is_active` is true, instead of always showing `"—"`.

2.15 WHEN the email page sidebar renders THEN the system SHALL show the Gmail connection status based on an actual OAuth state check, displaying "Connected" only when Gmail OAuth credentials are present and valid.

2.16 WHEN the user fills in the "Change password" form and clicks "Update password" THEN the system SHALL call the appropriate Supabase Auth password update API, and SHALL show a success toast only after the API call succeeds.

2.17 WHEN the user clicks "Delete my account" THEN the system SHALL show a confirmation dialog and, upon confirmation, SHALL call the account deletion API endpoint before removing the user's data.

2.18 WHEN the account settings page renders the "Connected accounts" section THEN the system SHALL reflect the actual OAuth connection state for Google and GitHub, showing "Connected" only when a valid OAuth token exists for that provider.

2.19 WHEN `schedule_followups` is called from an async endpoint THEN the system SHALL use an async Redis client (`redis.asyncio`) so that Redis operations do not block the event loop.

2.20 WHEN `_psycopg_url()` is called and `DATABASE_URL` does not contain `+asyncpg` THEN the system SHALL log a warning and either raise a configuration error or correctly construct the psycopg3 URL, preventing silent misconfiguration.

2.21 WHEN the user activates filter chips on the jobs page THEN the system SHALL pass the active filters as query parameters to `GET /jobs/applications` so that the displayed job list is actually filtered by the selected criteria.

2.22 WHEN the `ApplicationKanban` component renders THEN the system SHALL use stage names that exactly match the backend `VALID_STATUSES` values (`"saved"`, `"applied"`, `"viewed"`, `"interview"`, `"offer"`, `"rejected"`), ensuring cards appear in the correct columns.

2.23 WHEN a new user completes onboarding and selects "Anthropic" as their provider THEN the system SHALL default to a valid Anthropic model name (e.g., `claude-3-5-sonnet-20241022` or `claude-sonnet-4-5`) instead of the invalid `claude-sonnet-4-6`.

**LOW**

2.24 WHEN `internal.py` processes a request THEN the system SHALL verify the internal secret exactly once, using only the FastAPI dependency injection pattern, removing the redundant explicit call inside the handler body.

2.25 WHEN the user clicks "Generate Cover Letter" on the resume page THEN the system SHALL use a dedicated cover letter task type (or a resume task with a cover letter context flag) that does not require Gmail OAuth, so cover letter generation works independently of Gmail connection state.

2.26 WHEN the LinkedIn page renders the "Last analysis" banner THEN the system SHALL read `lastRun.started_at` (matching the backend `AgentRunResponse` field) instead of `lastRun.created_at`, so the timestamp displays correctly.

2.27 WHEN the agents page run history renders THEN the system SHALL read `run.started_at` from the backend `AgentRunResponse` for all timestamp displays, consistent with the backend schema.

2.28 WHEN `YOUTUBE_API_KEY` is set and `GET /interview-prep/videos` is called THEN the system SHALL successfully import `googleapiclient` because `google-api-python-client` SHALL be listed in `requirements.txt`.

2.29 WHEN any memory endpoint is called THEN the system SHALL call `await manager.initialize()` after constructing the `MemoryManager` in `_get_manager()`, ensuring the database connection pool is created before any memory operations are attempted.

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a valid authenticated request is made to any existing API endpoint not listed above THEN the system SHALL CONTINUE TO return the correct response with the same schema and HTTP status code as before.

3.2 WHEN a user uploads a resume PDF or DOCX THEN the system SHALL CONTINUE TO parse, chunk, embed, and store the document in the pgvector collection, returning the document ID and triggering ATS scoring.

3.3 WHEN a user submits a job application status update via `PATCH /jobs/applications/{id}/status` with a valid status THEN the system SHALL CONTINUE TO update the status and return the updated application record.

3.4 WHEN the email agent produces a draft and the user approves it via `POST /email/approve/{run_id}` THEN the system SHALL CONTINUE TO require explicit user approval before any email is sent — the human-in-the-loop gate SHALL NOT be bypassed by any fix.

3.5 WHEN a user's API key is stored or retrieved THEN the system SHALL CONTINUE TO encrypt API keys at rest using AES-256-GCM and SHALL CONTINUE TO never log or return plaintext key values.

3.6 WHEN a request arrives without a valid Supabase JWT THEN the system SHALL CONTINUE TO return HTTP 401 Unauthorized on all protected endpoints.

3.7 WHEN the rate limiter threshold is exceeded THEN the system SHALL CONTINUE TO return HTTP 429 Too Many Requests.

3.8 WHEN a user completes onboarding and saves preferences THEN the system SHALL CONTINUE TO persist `experience_level`, `job_type`, `work_mode`, `target_roles`, and `preferred_locations` via `PATCH /users/me/preferences`.

3.9 WHEN the resume page fetches documents THEN the system SHALL CONTINUE TO poll for ATS score updates every 3 seconds while `ats_score` is null, and stop polling once the score is available.

3.10 WHEN the applications Kanban board renders THEN the system SHALL CONTINUE TO allow drag-and-drop stage changes that call `PATCH /jobs/applications/{id}/status` with the new stage value.

3.11 WHEN `GET /jobs/applications` is called with a valid `status` query parameter THEN the system SHALL CONTINUE TO filter results to only applications matching that status.

3.12 WHEN the memory endpoints are called with a valid JWT THEN the system SHALL CONTINUE TO scope all memory operations to the authenticated user's ID, never returning or modifying another user's memories.

3.13 WHEN the agents page run history is displayed THEN the system SHALL CONTINUE TO filter runs by the currently selected agent type, showing only runs relevant to the active agent.

3.14 WHEN the dashboard fetches pending approvals THEN the system SHALL CONTINUE TO poll every 10 seconds and display all runs with `status === "awaiting_approval"`.

3.15 WHEN `POST /jobs/search` is called THEN the system SHALL CONTINUE TO enqueue a BullMQ job search task and return a `queue_job_id` with HTTP 200.

---

## Bug Condition Pseudocode

### Fix Checking — Critical Bugs

```pascal
// Bug 1.2 / 1.9: asyncio.run() inside executor thread
FUNCTION isBugCondition_AsyncioRun(X)
  INPUT: X = agent node invocation context
  OUTPUT: boolean
  RETURN X.called_via_run_in_executor = true
    AND X.sync_db_function_uses_asyncio_run = true
END FUNCTION

// Property: Fix Checking
FOR ALL X WHERE isBugCondition_AsyncioRun(X) DO
  result ← invoke_agent_node'(X)
  ASSERT result.status IN {"awaiting_approval", "completed", "failed"}
  ASSERT no RuntimeError raised
END FOR

// Bug 1.3: Missing const declaration for metrics array
FUNCTION isBugCondition_MetricsSyntax(X)
  INPUT: X = dashboard page render attempt
  OUTPUT: boolean
  RETURN X.metrics_array_has_no_const_declaration = true
END FUNCTION

FOR ALL X WHERE isBugCondition_MetricsSyntax(X) DO
  result ← render_dashboard'(X)
  ASSERT result.compiled_successfully = true
  ASSERT result.rendered_without_error = true
END FOR

// Bug 1.4: langchain_postgres.v2 import
FUNCTION isBugCondition_RagImport(X)
  INPUT: X = RAG service import attempt
  OUTPUT: boolean
  RETURN X.langchain_postgres_version = "0.0.17"
    AND X.import_path CONTAINS ".v2"
END FUNCTION

FOR ALL X WHERE isBugCondition_RagImport(X) DO
  result ← import_rag_service'(X)
  ASSERT result.import_error = null
  ASSERT result.PGVector_class_available = true
END FOR
```

### Fix Checking — High Bugs

```pascal
// Bug 1.7: .nullslast() vs .nulls_last()
FUNCTION isBugCondition_NullsLast(X)
  INPUT: X = GET /jobs/applications request
  OUTPUT: boolean
  RETURN X.sqlalchemy_method_called = "nullslast"
END FUNCTION

FOR ALL X WHERE isBugCondition_NullsLast(X) DO
  result ← list_applications'(X)
  ASSERT result.http_status = 200
  ASSERT result.attribute_error = null
END FOR

// Bug 1.6: Email compose schema mismatch
FUNCTION isBugCondition_ComposeSchema(X)
  INPUT: X = POST /email/compose request body
  OUTPUT: boolean
  RETURN X.body CONTAINS "subject"
    AND X.body CONTAINS "recipient"
    AND X.body NOT CONTAINS "company"
END FUNCTION

FOR ALL X WHERE isBugCondition_ComposeSchema(X) DO
  result ← compose_email'(X)
  ASSERT result.http_status != 422
END FOR
```

### Preservation Checking

```pascal
// Property: Preservation Checking — all non-buggy inputs
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT F(X) = F'(X)
  // Existing correct behavior is unchanged
END FOR
```
