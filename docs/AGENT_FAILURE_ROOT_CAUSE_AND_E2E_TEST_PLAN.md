# Agent Failure Root Cause and E2E Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the shared failure modes that make CareerCraft agents unavailable, silently degraded, or blocked, then prove all 15 agent paths and the RAG/HITL safety boundaries with repeatable tests.

**Architecture:** Fix shared boundaries first: worker-to-backend authentication, agent-run lifecycle/concurrency, portable structured LLM output, and explicit RAG embedding configuration. Keep agent-specific changes limited to migrating duplicate parsers and making degraded results explicit; validate the resulting system through backend regression tests plus a staging-only authenticated E2E smoke suite.

**Tech Stack:** Python 3.11, FastAPI, LangGraph, Pydantic, SQLAlchemy, PostgreSQL/pgvector, Redis/BullMQ, TypeScript worker, pytest, Docker Compose, curl/jq.

**Spec:** This document’s diagnosis, fix order, and E2E procedures below.

## Global Constraints

- Human-in-the-loop gate required before any email send or job application submit.
- API keys encrypted AES-256 before DB storage; never store plaintext in `user_model_settings.api_key_enc`.
- Agent actions always logged to `agent_runs` with status, input, output, tokens_used, and duration_ms.
- Never hardcode model names; resolve models through `llm_gateway.py`.
- LinkedIn/Naukri automation must use human-like delays and staging/throwaway postings for tests.
- Do not recreate production containers or query production data as part of the code change; production verification is an operator-run checklist.

## File Map

- Modify `backend/app/agents/_llm_json.py`: portable schema injection, JSON-fence tolerance, and retry behavior.
- Modify `backend/app/services/rag_service.py`, `backend/app/core/config.py`, and the RAG upload route: explicit embedding fallback and visible indexing warnings.
- Modify `backend/app/api/v1/agents.py`, `backend/app/services/workflow_service.py`, and `backend/app/core/database.py`: run-slot accounting, stale-run recovery, and production SQL logging defaults.
- Modify `backend/app/api/internal.py`, `worker/src/config.ts`, `worker/src/index.ts`, and worker processors: fail-fast internal-secret validation and authenticated startup health check.
- Modify agent parser/fallback modules under `backend/app/agents/`: use the shared JSON path and distinguish degraded output from successful output without fabricating user facts.
- Add focused regression tests under `backend/tests/unit/`, `backend/tests/integration/`, and `worker/test/`.
- Keep the operator-only curl/Docker procedures in this document; do not make production writes part of automated tests.
- Treat Part 4’s UI findings as follow-up triage; this plan verifies the backend contracts those screens consume and does not bundle a frontend redesign.

---

## Implementation Tasks

### Task 1: Lock down agent-run lifecycle and observability

**Files:**
- Modify: `backend/app/api/v1/agents.py`
- Modify: `backend/app/services/workflow_service.py`
- Modify: `backend/app/core/database.py`
- Test: `backend/tests/unit/test_agent_run_lifecycle.py` (create)
- Test: `backend/tests/integration/test_durable_workflows.py`

**Interfaces:**
- `POST /api/v1/agents/run` continues to return a run ID and must count only `queued` and `running` rows toward `AGENT_MAX_CONCURRENT_PER_USER`.
- `recover_expired_tasks()` remains the worker sweep entry point and must also expire abandoned approvals after 48 hours and fail timed-out `AgentRun` rows with a terminal error output.

- [ ] **Step 1: Write failing tests** for two `awaiting_approval` rows not producing `429`, a 49-hour approval becoming `expired`, and a timed-out `running` row becoming `failed` with `Worker did not report completion (timeout)`.
- [ ] **Step 2: Run** `pytest backend/tests/unit/test_agent_run_lifecycle.py backend/tests/integration/test_durable_workflows.py -q`; expect failures for the new assertions.
- [ ] **Step 3: Implement** the status filter, 48-hour approval expiry, per-agent timeout plus 60-second grace, and include active run IDs in a real concurrency `429`.
- [ ] **Step 4: Change** SQLAlchemy engine echo to `settings.APP_ENV != "production"` and delete unused `_run_agent_background` after confirming `rg "_run_agent_background" backend` has no callers.
- [ ] **Step 5: Run** the focused tests and `pytest backend/tests/unit/test_orchestrator.py -q`; expect PASS.
- [ ] **Step 6: Commit** with `git add backend/app/api/v1/agents.py backend/app/services/workflow_service.py backend/app/core/database.py backend/tests && git commit -m "fix: recover agent runs and free approval slots"`.

### Task 2: Make worker authentication fail closed

**Files:**
- Modify: `backend/app/api/internal.py`
- Create: `worker/src/config.ts`
- Modify: `worker/src/index.ts`
- Modify: `worker/src/processors/job-search.processor.ts`
- Modify: `worker/src/processors/followup.processor.ts`
- Modify: `worker/src/processors/status-check.processor.ts`
- Modify: `worker/src/processors/daily-search.processor.ts`
- Test: `worker/test/config.test.mjs` (create)

**Interfaces:**
- `GET /internal/health` must require the same internal-secret header and return `{"status":"ok"}`.
- `resolveInternalSecret(env)` must reject an empty `INTERNAL_SECRET`/`APP_SECRET_KEY`; worker startup must authenticate against `/internal/health` before consuming jobs.
- Processors receive the validated secret from the shared startup path; no processor may fall back to `""`.

- [ ] **Step 1: Write failing tests** for missing-secret startup failure, secret precedence, and a non-2xx health response preventing queue consumption.
- [ ] **Step 2: Run** `npm run build` and `node --test worker/test/config.test.mjs`; expect failures.
- [ ] **Step 3: Implement** `/internal/health`, `resolveInternalSecret`, and one startup health-check path in `worker/src/index.ts`; pass the validated value to processors instead of duplicating `?? ""` fallbacks.
- [ ] **Step 4: Run** `npm run build` and `node --test worker/test/config.test.mjs`; expect PASS.
- [ ] **Step 5: Commit** with `git add backend/app/api/internal.py worker && git commit -m "fix: fail closed when worker cannot authenticate"`.

### Task 3: Send the actual JSON schema and tolerate fenced output

**Files:**
- Modify: `backend/app/agents/_llm_json.py`
- Modify: `backend/app/agents/prompts/__init__.py`
- Test: `backend/tests/unit/test_llm_json.py` (create)
- Test: `backend/tests/unit/test_resume_agent.py`

**Interfaces:**
- `call_llm_json(llm, system_text, human_text, schema_cls)` still returns `schema_cls` and retries once, but every invocation includes `schema_cls.model_json_schema()` and parses bare or ```json-fenced output.

- [ ] **Step 1: Write failing tests** asserting the first message includes the schema, fenced JSON parses, and the retry also includes the schema.
- [ ] **Step 2: Run** `pytest backend/tests/unit/test_llm_json.py backend/tests/unit/test_resume_agent.py -q`; expect failures.
- [ ] **Step 3: Implement** a small `_strip_fences()` helper, serialize the Pydantic schema into the system prompt, and include the schema in the retry prompt; remove misleading example field names from `_COMMON`.
- [ ] **Step 4: Run** the focused tests plus `pytest backend/tests/unit/test_cover_letter_agent.py backend/tests/unit/test_followup_agent.py -q`; expect PASS.
- [ ] **Step 5: Commit** with `git add backend/app/agents backend/tests/unit/test_llm_json.py backend/tests/unit/test_resume_agent.py && git commit -m "fix: provide schemas to agent JSON calls"`.

### Task 4: Make RAG embedding configuration explicit and visible

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/rag_service.py`
- Modify: `backend/app/api/v1/rag.py`
- Test: `backend/tests/unit/test_rag_embedding_config.py` (create)
- Test: `backend/tests/integration/test_rag_pipeline.py`

**Interfaces:**
- Add `EMBEDDING_PROVIDER` as an explicit optional setting (`openai`, `google`, or `ollama`). Chat providers without native embeddings must raise a clear configuration error when it is unset.
- RAG upload preserves HTTP 201/document creation while returning `DocumentResponse.warning` when indexing fails; retrieval exposes an unavailable-context marker for agent warnings.

- [ ] **Step 1: Write failing tests** for native-provider selection, missing fallback configuration, and upload warning propagation.
- [ ] **Step 2: Run** `pytest backend/tests/unit/test_rag_embedding_config.py backend/tests/integration/test_rag_pipeline.py -q`; expect failures.
- [ ] **Step 3: Implement** provider selection without changing existing provider-namespaced collection names, log the indexing exception, and return the existing warning field.
- [ ] **Step 4: Run** the focused tests and confirm an indexed fixture has non-null `embedded_at`; expect PASS.
- [ ] **Step 5: Commit** with `git add backend/app/core/config.py backend/app/services/rag_service.py backend/app/api/v1/rag.py backend/tests && git commit -m "fix: surface and configure RAG embedding failures"`.

### Task 5: Migrate duplicate JSON parsers and make degraded results honest

**Files:**
- Modify: `backend/app/agents/harness.py`
- Modify: `backend/app/agents/interview_coach_agent.py`
- Modify: `backend/app/agents/interview_prep_agent.py`
- Modify: `backend/app/agents/job_search.py`
- Modify: `backend/app/agents/nl_search_agent.py`
- Modify: `backend/app/agents/salary_agent.py`
- Modify: `backend/app/agents/resume_agent.py`
- Modify: `backend/app/agents/linkedin_agent.py`
- Modify: `backend/app/agents/email_agent.py`
- Test: `backend/tests/unit/test_job_search_agent.py`
- Test: `backend/tests/unit/test_interview_coach_agent.py`
- Test: `backend/tests/unit/test_salary_agent.py`
- Test: `backend/tests/unit/test_linkedin_agent.py`
- Test: `backend/tests/unit/test_email_agent.py`
- Test: `backend/tests/unit/test_followup_agent.py`
- Test: `backend/tests/unit/test_agent_degraded_results.py` (create)

**Interfaces:**
- `job_search.py` uses `job_search_prompt.OUTPUT_SCHEMA`; `nl_search_agent.py` uses `nl_search_prompt.OUTPUT_SCHEMA`; `interview_prep_agent.py` uses `interview_prep_prompt.OUTPUT_SCHEMA`; `interview_coach_agent.py` uses `interview_coach_prompt.OUTPUT_SCHEMA` for both question and evaluation responses; `salary_agent.py` uses `salary_prompt.OUTPUT_SCHEMA`; `harness.py` keeps its existing `ReflectOutput` path and only replaces the raw learning-entry parse if that path is still reachable.
- A live-model/embedding failure is logged with traceback and returned as an explicit degraded/failed result; fallback output may reuse retrieved user text but may not invent resume, profile, or email facts. HITL remains mandatory for actions that already require approval.

- [ ] **Step 1: Add one regression test per migrated parser** for fenced valid JSON and one failure test asserting no fabricated boilerplate is presented as a normal success.
- [ ] **Step 2: Run** the affected unit tests; expect parser/fallback assertions to fail.
- [ ] **Step 3: Add only the missing Pydantic models** beside the existing prompt schemas and route each parser through `call_llm_json`; do not add a new parsing framework.
- [ ] **Step 4: Replace `logger.error(... %s, exc)` with `logger.exception(...)`** on the fallback paths and mark degraded output in the existing result shape so the UI can branch without a new status unless current contracts require one.
- [ ] **Step 5: Run** `pytest backend/tests/unit -q`; expect all existing HITL tests to remain green.
- [ ] **Step 6: Commit** with `git add backend/app/agents backend/tests/unit && git commit -m "fix: make agent parsing and degradation explicit"`.

### Task 6: Add a repeatable staging E2E harness for all agents

**Files:**
- Modify: `scripts/run_e2e_tests.sh`
- Modify: `backend/tests/e2e/conftest.py`
- Modify: `backend/tests/e2e/test_careercraft_full.py`
- Test: `backend/tests/e2e/test_agent_failure_regression.py` (create)

**Interfaces:**
- E2E tests run only when `INTEGRATION=1`, use an authenticated staging user and fixture resume, and never send email or submit an application without an explicit test approval step.
- The suite covers RAG upload, orchestrator routing, all 15 agent routes, both auto-apply checkpoints, run terminal status, token/duration logging, and absence of parse/vector/fallback errors.

- [ ] **Step 1: Add shared fixtures** for `API`, bearer token, JSON headers, fixture resume, polling with the AGENTS.md timeout table, and log capture.
- [ ] **Step 2: Add one test per T0–T15 procedure** from Part 3 below; assert user-specific output, `tokens_used > 0`, terminal status, and no forbidden send/submit side effect.
- [ ] **Step 3: Add negative tests** for invalid task type, missing model/embedding configuration, rejected email approval, rejected auto-apply approvals, and recruiter-replied follow-up cancellation.
- [ ] **Step 4: Run** `INTEGRATION=1 bash scripts/run_e2e_tests.sh`; expect PASS only against staging services with configured provider keys.
- [ ] **Step 5: Commit** with `git add scripts/run_e2e_tests.sh backend/tests/e2e && git commit -m "test: cover agent failure modes end to end"`.

### Task 7: Execute the operator verification and close the loop

**Files:**
- Modify: this document only, recording observed results and dates.

- [ ] **Step 1: Run** the six preconditions in Part 3.0, including `--force-recreate scheduler temporal-worker` only with explicit production operator approval.
- [ ] **Step 2: Run** the per-agent T0–T15 checks in staging and the 60-minute full-loop smoke test.
- [ ] **Step 3: Record** failed checks against RC-1 through RC-10; do not call a degraded/fallback result a pass.
- [ ] **Step 4: Run** the complete backend suite: `pytest --collect-only -q` followed by `pytest backend/tests -q`.
- [ ] **Step 5: Commit** the completed checklist separately from code changes with `git add docs/AGENT_FAILURE_ROOT_CAUSE_AND_E2E_TEST_PLAN.md && git commit -m "docs: record agent failure verification"`.

---

# Why No Agent Works — Root Cause, Fixes, E2E Test Plan, and UI Bug List

**Date:** 2026-09-22
**Scope:** all 15 agents + RAG, all 20 authenticated screens
**Method:** production log evidence + code trace. Tasks 1–6 are implemented on the current branch; production verification in Task 7 remains operator-run.

---

## 0. TL;DR

"None of the agents work" is not one bug. It is **four independent failures stacked on top of each other**, plus a fifth that hides all of them from you:

| # | Failure | Kills |
|---|---|---|
| **RC-1** | `INTERNAL_SECRET` mismatch → Node scheduler gets `403` from `/internal/*` | JobSearch, NLSearch, FollowUp, EmailMonitor, daily-search |
| **RC-2** | The JSON schema is **never sent to the model** — prompts say "matching the schema given" and then don't give it | Resume, CoverLetter, JobSearch scoring, FollowUp, InterviewPrep, InterviewCoach, Salary, NLSearch |
| **RC-3** | RAG embeddings silently default to an **Ollama server that isn't running** | All 15 agents lose all RAG context |
| **RC-4** | Agents catch their own exception and return `awaiting_approval` with canned filler | Resume, LinkedIn, Email, InterviewPrep — failures look like successes |
| **RC-5** | Stale `awaiting_approval` rows trip the concurrency gate → every `/agents/run` returns `429` | Everything on `/agents` and the dashboard quick actions |

Fix order matters: **RC-1 → RC-5 → RC-2 → RC-3 → RC-4**. RC-1 and RC-5 are minutes of work and unblock testing of everything else.

---

# Part 1 — Root Causes

## RC-1 — Stale `INTERNAL_SECRET` in the `scheduler` container → `403 Forbidden`

### Evidence

Production scheduler logs, every queued job:

```
POST /internal/agents/run-job-search  status=403 body={"detail":"Forbidden"}
POST /internal/agents/status-check    status=403 body={"detail":"Forbidden"}
POST /internal/agents/daily-search    status=403 body={"detail":"Forbidden"}
```

Container/secret timeline on `oraclevm`:

| Artifact | Timestamp |
|---|---|
| `/opt/careercraft-secrets/backend.env` (mtime) | `2026-09-21 08:17:37 UTC` |
| `backend` container started | `2026-09-21 19:46:48 UTC` ✅ after |
| `scheduler` container started | `2026-09-19 09:49:31 UTC` ❌ **before** |
| `temporal-worker` container started | `2026-09-20 19:38:04 UTC` ❌ **before** |

`env_file:` is resolved by Docker at **container-create** time and baked into the container config. `docker restart` re-runs the entrypoint with the *old* baked env. The scheduler is still presenting the pre-rotation secret.

Verification side:

```python
# backend/app/api/internal.py
def _verify_secret(x_internal_secret: str = Header(...)) -> None:
    internal_secret = settings.INTERNAL_SECRET or settings.APP_SECRET_KEY
    if not hmac.compare_digest(x_internal_secret, internal_secret):
        raise HTTPException(status_code=403, detail="Forbidden")
```

Caller side:

```ts
// worker/src/processors/job-search.processor.ts
const INTERNAL_SECRET = process.env.INTERNAL_SECRET ?? process.env.APP_SECRET_KEY ?? "";
await axios.post(`${BACKEND_URL}/internal/agents/run-job-search`, {...},
  { headers: { "x-internal-secret": INTERNAL_SECRET }, timeout: 130_000 });
```

Note the `?? ""` fallback — if `INTERNAL_SECRET` is unset the worker cheerfully sends an empty string and gets a 403 rather than crashing at boot.

### Blast radius

Everything routed through the Node worker (`agent-queue`):
`job-search`, `followup-email`, `status-check` (EmailMonitor, every 6 h), `daily-search` (every 24 h).
NLSearch delegates to JobSearch, so it dies too.

### Fix

**Immediate (production, one command):**

```bash
docker compose -f deploy/oracle/compose.yml up -d --force-recreate scheduler temporal-worker
```

`--force-recreate`, **not** `docker restart` — restart reuses the baked env.

**Root-cause fix (so this can't silently recur):** fail loudly instead of sending `""`.

```ts
// worker/src/processors/job-search.processor.ts (and siblings)
const INTERNAL_SECRET = process.env.INTERNAL_SECRET ?? process.env.APP_SECRET_KEY;
if (!INTERNAL_SECRET) throw new Error("INTERNAL_SECRET/APP_SECRET_KEY not set — refusing to start");
```

Put this at module scope in `worker/src/index.ts` once, not per-processor.

**Also add:** a startup self-check — the worker pings `GET /internal/health` with its secret on boot and exits non-zero on 403. A container that can't authenticate should not sit there consuming jobs and failing them.

---

## RC-2 — The output schema is never sent to the model

This is the single biggest code defect, and it affects every agent that asks for JSON.

### Evidence

The shared system prompt promises a schema:

```python
# backend/app/agents/prompts/__init__.py — _COMMON rule (2)
"Output ONLY a single JSON object matching the schema given — no markdown fences, no commentary..."
```

The schema is never given. `call_llm_json` is the only shared JSON path and it sends exactly two messages:

```python
# backend/app/agents/_llm_json.py
def call_llm_json(llm, system_text, human_text, schema_cls):
    messages = [SystemMessage(content=system_text), HumanMessage(content=human_text)]
    response = llm.invoke(messages)
    content = response.content if isinstance(response.content, str) else str(response.content)
    try:
        return schema_cls.model_validate_json(content)
    except ValidationError as exc:
        ...retry with "Return ONLY valid JSON matching the schema."   # still no schema
```

Grep across `backend/app` for every mechanism that would have supplied one:

```
model_json_schema | with_structured_output | JsonOutputParser | PydanticOutputParser
→ 0 matches
```

The model is being asked to guess field names. Production logs show exactly that — it guesses from the **input labels in the prompt**:

```
LLM JSON parse failed, retrying once: 1 validation error for ResumeOutput
summary  Field required [type=missing, input_value={'target_title': ...}]
LLM JSON parse failed, retrying once: ... input_value={'resume_markdown': '# Pr...}
LLM JSON parse failed, retrying once: ... 'red_flags': []
```

- `target_title` — lifted from `TARGET_TITLE:` in `build_user_prompt`.
- `red_flags` — lifted from `_COMMON` rule (7), which mentions "notes/warnings/red_flags/blockers" as prose.

The model is doing the only reasonable thing with the information it was given.

### Second defect in the same function: no fence stripping

`model_validate_json(content)` is called on raw content. A model that replies

````
```json
{"resume_markdown": "...", "summary": "..."}
```
````

fails validation **even when the JSON is perfectly correct**. The hand-rolled parsers elsewhere in the codebase do strip fences (`raw.rstrip("`").strip()` in `interview_coach_agent.py:209`, `salary_agent.py:202`) — the shared helper does not. Six agents hand-roll `json.loads` precisely because the shared helper doesn't work: `harness.py`, `interview_coach_agent.py`, `interview_prep_agent.py`, `job_search.py`, `nl_search_agent.py`, `salary_agent.py`.

### Blast radius

`call_llm_json` callers: `resume_agent.py:131`, `cover_letter_agent.py:151`, `followup_agent.py:156`, `job_search.py:2013`.
Hand-rolled-JSON agents hit the same "no schema" problem with a different parser: InterviewCoach, InterviewPrep, Salary, NLSearch.

That is **8 of 15 agents** producing garbage or fallback output.

### Fix — one place, all callers

`call_llm_json` is the correct single point. Two changes:

```python
# backend/app/agents/_llm_json.py
import json

def call_llm_json(llm, system_text: str, human_text: str, schema_cls: type[BaseModel]):
    schema_text = json.dumps(schema_cls.model_json_schema(), separators=(",", ":"))
    system = f"{system_text}\n\nJSON_SCHEMA (your output MUST validate against this):\n{schema_text}"
    messages = [SystemMessage(content=system), HumanMessage(content=human_text)]
    ...
    return schema_cls.model_validate_json(_strip_fences(content))


def _strip_fences(text: str) -> str:
    """Models wrap JSON in ```json fences despite instructions. Tolerate it."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1].rsplit("```", 1)[0]
    return t.strip()
```

Apply `_strip_fences` on the retry path too, and include the schema in the retry message.

**Preferred alternative where the provider supports it:** `llm.with_structured_output(schema_cls)`. Anthropic, OpenAI and Google all support it; Ollama/NIM do not reliably. Since this is a BYOK app that must work on all five providers, the schema-in-prompt fix above is the portable one. Ship that first; layer `with_structured_output` behind a provider capability check later if measured parse failures justify it.

**Then migrate the 6 hand-rolled parsers onto `call_llm_json`.** Each needs a Pydantic model in `app/agents/prompts/`. This is the larger half of the work and can follow in a second PR — but leaving them means those agents keep failing after the first fix lands.

**Also fix the lying prompt:** `_COMMON` rule (7) listing "notes/warnings/red_flags/blockers" as example key names is actively harmful — the model treats them as required. Delete the example key names; the schema now carries that information.

---

## RC-3 — RAG embeddings default to an Ollama server that does not exist

### Evidence

Production log, on every agent run:

```
Vector retrieval failed for b9d3a177-…/resume: Failed to connect to Ollama …
```

```python
# backend/app/services/rag_service.py
def get_embedding_model(model_settings):
    provider = model_settings.provider
    if provider == "openai":  return OpenAIEmbeddings(model="text-embedding-3-small", api_key=api_key)
    if provider == "google":  return GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", ...)
    if provider == "ollama":  return OllamaEmbeddings(model="nomic-embed-text", base_url=model_settings.ollama_url)
    # anthropic + nvidia_nim have no native embedding API — fall back to local nomic-embed-text
    return OllamaEmbeddings(model="nomic-embed-text")   # ← http://localhost:11434, not in the container
```

`claude-sonnet-4-6` is the documented primary model. Anthropic has no embeddings API, so **the default configuration lands on the broken branch.** Same for `nvidia_nim`, `openrouter`, `opencode`, `deepseek`.

Two silent-failure layers make this invisible:

1. `retrieve()` swallows the exception (`logger.warning(...)`) and falls back to one chunk of `fetch_user_profile_text(user_id)` — `raw_text[:2000]`, and **only** for `doc_type == "resume"` with `is_primary=True`. Every other doc type returns nothing.
2. Upload swallows it too:

```python
# backend/app/api/v1/rag.py:131-148
embedded_at = None
if model_settings:
    try:
        ingest_document(...)
        embedded_at = datetime.now(timezone.utc)
    except Exception:
        # Embedding failed — document saved without vectors, can retry later
        embedded_at = None
```

Bare `except Exception:` with no log line at all. The document row is created with `embedded_at = None` and the API returns `201`. The UI shows the upload as successful.

### Blast radius

Every agent. Resume tailoring works off 2000 truncated characters instead of 8 retrieved chunks; achievements, certifications, portfolio and notes collections are never consulted at all.

### Fix

**1. Stop defaulting to a host that isn't there.** Make the embedding provider explicit and independent of the chat provider:

```python
# rag_service.py
_EMBEDDING_FALLBACK = settings.EMBEDDING_PROVIDER  # e.g. "openai" | "google" | "ollama"

def get_embedding_model(model_settings):
    provider = model_settings.provider
    if provider in _NATIVE_EMBEDDING_PROVIDERS:
        return _build(provider, model_settings)
    if not _EMBEDDING_FALLBACK:
        raise EmbeddingUnavailable(
            f"Provider '{provider}' has no embeddings API and EMBEDDING_PROVIDER is unset. "
            "Set EMBEDDING_PROVIDER (openai/google/ollama) in backend env."
        )
    return _build(_EMBEDDING_FALLBACK, model_settings)
```

Note the collection name already includes provider + dimension (`{user_id}_{doc_type}_{provider}_{dim}d`), so switching embedding providers won't corrupt existing collections — it creates new ones. Users will need a re-ingest; add a "Re-index documents" button (see UI-12).

**2. Surface the failure at upload.** Log it, and return it:

```python
except Exception as exc:
    logger.warning("Embedding failed for doc_type=%s user=%s: %s", doc_type, current_user.id, exc)
    upload_warning = (upload_warning or "") + " Document saved but not indexed for AI search — check Settings → Models."
    embedded_at = None
```

`DocumentResponse.warning` already exists and is already rendered. Zero frontend work.

**3. Surface it at retrieval.** `retrieve()` should put a flag on the returned context so the agent can add `"RAG context unavailable"` to `warnings` instead of quietly producing a worse answer.

**4. Backfill:** a management command that re-embeds every `UserDocument` where `embedded_at IS NULL`.

---

## RC-4 — Agents report failure as success

**Correction after full-code audit (2026-09-22):** the first pass of this document guessed this pattern applied broadly. Having now read all 15 agent modules line-by-line, the actual split is:

| Fabricates content + reports success | Fails honestly (`status:"failed"`, no fake content) |
|---|---|
| `resume_agent.py` | `cover_letter_agent.py` |
| `linkedin_agent.py` | `interview_coach_agent.py` (both nodes) |
| `email_agent.py` (`_fallback_email`, only when a recipient was given — otherwise `completed` with the fabricated draft, which is arguably worse) | `nl_search_agent.py` |
| `interview_prep_agent.py` (`_fallback_prep`) | `linkedin_outreach_agent.py` |
| | `email_monitor_agent.py` |
| | `company_research_agent.py` (returns real partial data + a `partial_data` failures dict — this is the honest way to do graceful degradation) |
| | `job_search.py` `_score_job`/`_score_job_quick` (falls back to `_heuristic_score_job`, a real deterministic keyword-overlap score — not fabricated text) |

`cover_letter_agent.py` and `interview_coach_agent.py` are the reference implementations for "fail don't fake" — RC-4's fix should make the other four match their pattern, not invent a new one.

**RC-4-lite (same root cause, smaller blast radius):** `salary_agent.py::_generate_negotiation_script` falls back to a hardcoded templated negotiation script on JSON parse failure, and — unlike the agent-level fallbacks above — **splices it into an otherwise-real report with no flag**. The user gets a real market percentile report with a possibly-templated script and no way to tell which. `company_research_agent.py`'s pgvector embed step and `thinking.py`'s `think_and_select`/`think_about_job_match` also degrade silently (caught, logged, empty string returned) — lower stakes since they feed an intermediate reasoning step rather than the final artifact, but the same "silent degradation, no signal" pattern.

### Evidence

```python
# backend/app/agents/resume_agent.py:164-200
except Exception as exc:
    logger.error("Resume agent failed for user %s: %s", user_id, exc)
    ...
    return {
        **state,
        "status": "awaiting_approval",          # ← looks identical to a real success
        "pending_action": _resume_pending_action(fallback, pdf_document_id),
        ...
    }
```

with

```python
def _fallback_resume_text(context_text, full_name, jd_text):
    ...
    "Software professional focused on practical delivery and reliable product outcomes."
```

Same pattern in `linkedin_agent.py` (hardcoded `_HEADLINE_PROMPT` / `_ABOUT_PROMPT` / `_BULLETS_PROMPT` strings, `thinking: "Fallback draft used because live model call failed."`), `email_agent.py:116` (`_fallback_email`), `interview_prep_agent.py:122,149` (`_fallback_prep`).

Production correlation: **3 × `POST /api/v1/resume/optimize → 200`** in the same window as **5 × `LLM JSON parse failed`**. All three "successful" responses were boilerplate.

Additional wrinkle: the `logger.error("Resume agent failed …")` line does **not** appear in production logs even though the `logger.warning` from `_llm_json.py` does. Either the module logger level is misconfigured or the exception is being swallowed before reaching line 165 — worth 10 minutes with `LOG_LEVEL=DEBUG` after RC-2 lands, but it doesn't change the diagnosis.

### Fix

A fallback is a legitimate product decision. Reporting it as a normal result is not. Three changes:

1. **Distinct status.** Return `status: "completed_degraded"` (new) or keep `awaiting_approval` but set `result["degraded"] = True`. The latter is a smaller diff and the frontend can branch on one boolean.
2. **Never fabricate.** `_fallback_resume_text` invents a professional summary the user never wrote. Return the retrieved resume text verbatim, or return nothing — do not generate plausible-looking content and present it as a tailored resume.
3. **Log at `exception` level with the traceback**: `logger.exception("Resume agent failed for user %s", user_id)` — `logger.error` with `%s` on the exception discards the stack.

---

## RC-5 — Stale `awaiting_approval` rows permanently return `429`

**Sharpened after full-code audit:** this isn't just a theoretical gate-counting issue — three frontend pages create rows they can never resolve, every single time they're used successfully.

`resume_agent_node` and `cover_letter_node` both return `status: "awaiting_approval"` on success (confirmed by direct read). `interview_prep_agent_node`'s pending-action type `"interview_prep"` is listed in `workflow_service.py`'s `DRAFT_TYPES`, confirming it too is an approval-gated type. All three are called from inline synchronous endpoints (`/resume/optimize`, `/cover-letter/generate`) or the durable path, and:

```tsx
// frontend/src/app/(app)/resume/page.tsx — optimizeMutation.onSuccess
onSuccess: (data) => {
  if (data.resume_markdown) setResumePreviewText(data.resume_markdown);
  ...
  toast.success(data.ats_score != null ? `Resume tailored! ATS score ${data.ats_score}.` : "Resume tailored.");
  // no data.run_id captured, no POST /agents/{run_id}/approve — ever
},
```

`grep -n "/approve" resume/page.tsx cover-letter/page.tsx interview-prep/page.tsx` → **zero matches in all three files.** Compare `salary/page.tsx:52` and `linkedin/outreach/page.tsx:46`, which do call `POST /agents/{id}/approve` and are not affected.

The result: **every successful resume tailor, cover letter generation, or interview prep run leaves a permanent `awaiting_approval` row**, while the UI tells the user "Resume tailored!" — success, not "waiting for your review." Two uses of any combination of these three features and the concurrency gate (`max_concurrent = 2`) locks the user out of `/agents/run` entirely, with no UI affordance to see or clear the orphaned rows.

### Evidence (original)

```python
# backend/app/api/v1/agents.py
AgentRun.status.in_(["queued", "running", "awaiting_approval"])
...
raise HTTPException(status_code=429, detail=f"Max {max_concurrent} concurrent agent runs reached...")
```

`max_concurrent = 2`. The gate counts `awaiting_approval`, which is **not a running task** — it is a row waiting for a human that may never come back.

Meanwhile the **inline synchronous endpoints** each create an `AgentRun` and leave it in `awaiting_approval`:

`/resume/optimize`, `/cover-letter/generate`, `/salary/report`, `/company/research`, `/interview/session/*`, `/email/compose`, `/linkedin/outreach/identify`.

```python
# backend/app/api/v1/resume.py:64-130
agent_run = AgentRun(status="running")
...
agent_run.status = result_state["status"]     # = "awaiting_approval"
```

**Two resume optimizations and every `/agents/run` call is blocked forever.** The `/agents` page, the dashboard quick actions, `/linkedin`, `/interview-prep` — all `429`.

There is no UI to clear these except the dashboard's pending-approvals panel, which only renders runs whose `output` shape it recognises.

### Fix

Root cause is that a human-review state is being counted as a compute slot. Two independent corrections, both needed:

1. **Don't count review states against concurrency:**
   ```python
   AgentRun.status.in_(["queued", "running"])
   ```
   That is the whole fix for the 429. `awaiting_approval` consumes no worker.

2. **Expire abandoned approvals.** Add to the existing `recover_expired_tasks` sweep:
   ```python
   # anything awaiting approval for >48h is abandoned
   UPDATE agent_runs SET status='expired'
   WHERE status='awaiting_approval' AND started_at < now() - interval '48 hours';
   ```

3. **Return a useful 429.** Current detail is `"Max 2 concurrent agent runs reached..."` with no run IDs. Include them so the UI can offer "cancel these".

4. **Fix the three pages that orphan their own runs.** Two options, pick per-page:
   - Cheapest: after a successful `/resume/optimize` / `/cover-letter/generate` / interview-prep response, immediately `POST /agents/{run_id}/approve {"approved": true}` in `onSuccess` before showing the "tailored!" toast — the review already happened implicitly (the user is looking at the draft on the page).
   - More correct: these three pages should treat the response the same way `/agents` does — show the draft with real Approve/Discard actions, and only call `/approve` when the user acts. Either way, `data.run_id` must be captured (it currently isn't retained by any of the three pages' response types).

   Fix #2 in RC-5's own list (dropping `awaiting_approval` from the gate) prevents the 429 symptom either way, but does not stop the DB from accumulating permanently-open approval rows — do this fix too.

---

## RC-6 — Runs stuck in `running` forever

After the RC-1 403, nothing ever writes a terminal status. Run `08826ac0-e737-469c-81b1-20fa8c9eac23` has been `running` for over 24 hours; the frontend polled `GET /api/v1/agents/runs/08826ac0-…` **106 times**. The Jobs page spinner never stops.

**Fix:** `recover_expired_tasks` already exists for `WorkflowTask`. Extend it to `AgentRun`: any run in `running` past its `AGENT_TIMEOUTS[agent_type]` + 60 s grace → `status='failed'`, `output={'error': 'Worker did not report completion (timeout)'}`. Without this, *any* worker crash produces an immortal spinner.

---

## RC-7 — `_run_agent_background` is dead code

`backend/app/api/v1/agents.py:77`. Zero callers (grep-verified). It is a plausible-looking second execution path that sends anyone debugging this system down the wrong road.

**Fix:** delete it.

---

## RC-8 — `user_settings` is fetched, decrypted, then thrown away

`harness.py` resolves the user's model settings and decrypts the API key, then builds `AgentState` (lines 198–208) **without** them. Every node then re-queries the DB via `fetch_model_settings(user_id)` and re-decrypts.

Not currently causing a failure — but it means N extra DB round-trips and N extra AES decryptions per run, and it's why `salary.py` calls `harness.run(..., user_settings={})` with an empty dict and gets away with it.

**Fix:** put `model_settings` into `AgentState` in the harness; have `fetch_model_settings` calls in nodes read from state with a DB fallback. Low priority — do it after the functional fixes.

---

## RC-9 — `save-to-drive` → 502

One occurrence in production. `rag.py:255-297` maps `DriveError` → 502 with the real Google reason. Needs a live retry post-RC-1 to see the actual message. Likely a Nango token/scope issue, not an agent bug.

---

## RC-10 — SQLAlchemy `echo` is on in production

Backend and agent-worker logs are flooded with full SQL statements. This is why RC-1's 403s and RC-2's parse failures went unnoticed for days. **Fix:** `echo=settings.DEBUG` in the engine constructor.

---

## RC-11 — Two call sites return `status: "error"`, a value no consumer recognises

Found reading `orchestrator.py` and `agentStore.ts` side by side.

```python
# job_search.py:1971, 1977 — required-context validation
return {**state, "status": "error", "error": "missing: titles (or search_query)"}
return {**state, "status": "error", "error": "missing: active model settings"}
# resume_agent.py:192 — fallback PDF generation itself failing
return {**state, "status": "error", "error": str(se)}
```

`AgentState.status` is documented (AGENTS.md) as one of `running, awaiting_approval, completed, failed`. `_make_node_runner` in `orchestrator.py` branches on exactly three values — `awaiting_approval`, `failed`, `completed` — to decide which SSE event to emit:

```python
if status == "awaiting_approval": emit(..., "checkpoint", ...)
elif status == "failed": emit(..., "error", ...)
elif status == "completed": emit(..., "complete", ...)
# no branch for "error" — nothing is emitted
```

And the frontend's `AgentRun["status"]` union (`agentStore.ts:19`) is `"queued" | "running" | "awaiting_approval" | "completed" | "failed" | "needs_verification"` — no `"error"` member either. `runStatus()` in `agents/page.tsx` falls through to its default case for any unrecognised value: `{ label: "Running", icon: Clock3, className: "text-primary" }`.

Net effect: a job search with a missing/empty query, or a resume run whose fallback PDF generation also fails, becomes a **run that is actually terminal but displays as "Running" forever** — no SSE event, no toast, badge stuck on the primary-colored "Running" pill. This is a second, independent cause of the stuck-spinner symptom (UI-10), unrelated to RC-1/RC-6.

**Fix:** change both call sites to `"status": "failed"`. Two-line diff, no other code changes needed — `"failed"` already has correct handling everywhere.

---

## RC-12 — Frontend field/action-type drift between agents and their UI

Three small but real mismatches, found by cross-referencing each agent's actual output shape against the component that renders it:

1. **`ApprovalModal.tsx` has no renderer for 7 of the ~13 `pending_action.type` values it can receive** — `linkedin_outreach` (from `linkedin_outreach_agent.py`), `salary_report_review`, `interview_prep`, `auto_apply_approval`, `review_application_draft`, and others all fall through to the generic `<pre>{JSON.stringify(action, null, 2)}</pre>` block (line 329 area). The user approving a LinkedIn outreach batch, for instance, sees raw JSON with contact names and message bodies instead of the drafted-message cards the data supports.
2. **`semantic_memory.py::_heuristic_memories`** checks `output.get("resume_text")` to decide whether to save a "resume agent produced a tailored resume" memory (line 226) — but `resume_agent.py`'s actual output key is `resume_markdown`. This check can never be true; the resume-specific memory heuristic is dead code. Low severity (degrades memory quality only), but the same "two systems evolved independently, field names drifted" root cause as RC-2's `target_title`/`red_flags` leakage.
3. Stale `.pyc` files exist under `backend/app/agents/__pycache__/` for modules that no longer have `.py` sources (`*_v2.py` variants of nearly every agent — `resume_agent_v2`, `job_search_agent_v2`, etc.). No live `.py` file imports them, so they are inert, but they indicate an abandoned parallel rewrite and are worth deleting so a future `grep`/audit doesn't chase them. `find backend -name '__pycache__' -exec rm -rf {} +`.

**Fix for #1:** add renderers for the missing types, or better, key `ApprovalModal` off a small type-to-component map instead of a chain of `actionType === "..."` conditionals — that map makes it structurally obvious when an agent's output type has no reviewer UI, instead of silently falling through to JSON.

---

# Part 1.5 — Verified Per-Agent Audit (all 15, read line-by-line 2026-09-22)

Confidence: **Verified** = read the actual node function and its error paths. Everything in Part 1 above was already Verified; this table is the compact summary plus what's newly confirmed.

| Agent | RC-2 exposure (schema not sent) | RC-4 (fakes success) | Own bugs found |
|---|---|---|---|
| Orchestrator | n/a | n/a | RC-11 (no `"error"` status handling) |
| JobSearch | Yes (`call_llm_json` in scoring loop) | **No** — falls back to real heuristic score | `status:"error"` on validation failure (RC-11); scoring loop has no per-batch try/except, one bad batch fails the whole search |
| NLSearch | Yes (hand-rolled `json.loads`) | **No** — fails honestly | Duplicated fence-strip logic (4th copy in the codebase) |
| Resume | Yes | **Yes** — fabricates a generic summary | Leaves `awaiting_approval` forever (RC-5) |
| CoverLetter | Yes | **No** — reference-quality error handling | RAG-fallback-to-profile-text is a good pattern; also leaves `awaiting_approval` forever (RC-5) |
| LinkedIn | Yes | **Yes** — hardcoded prompt text as `thinking` | — |
| LinkedInOutreach | No LLM-JSON call for message content | **No** — honest empty-result and failure paths | Message type has no `ApprovalModal` renderer (RC-12) |
| Email | Hand-rolled `"Subject:"` line split, no schema | **Yes**, but only when a recipient was supplied — otherwise the fabricated draft is returned as `status: "completed"`, which is arguably worse | — |
| EmailMonitor | Regex-first, LLM only for ambiguous cases | **No** — fails honestly | `_extract_company_regex` is weak; most classified notifications likely resolve to `UNKNOWN` and never update application status |
| FollowUp | Yes (`call_llm_json`) | Falls back to a generic template with no flag distinguishing it from a personalized draft | Redis `SET NX` scheduling is genuinely well-engineered (atomic, self-healing on enqueue failure) |
| InterviewCoach | Yes (hand-rolled, duplicated fence-strip x2) | **No** — reference-quality error handling | — |
| InterviewPrep | Yes (hand-rolled) | **Yes** — `_fallback_prep` | Leaves `awaiting_approval` forever (RC-5) |
| CompanyResearch | No LLM-JSON call | **No** — real partial data + `partial_data` failures dict is the correct pattern | Embed failures logged but not surfaced in `result` |
| Salary | Yes (hand-rolled) | **No** at agent level, **RC-4-lite** in `_generate_negotiation_script` | — |
| AutoApply | Delegates to ResumeAgent (inherits its RC-4) + own hand-rolled cold-email/LinkedIn-note generation (no schema, catch-all `except: return None`) | Sub-generators return `None` silently on failure rather than fabricating | **HITL design verified sound**: `workflow_service.continue_action` + `application_workflow.run_application_stage` implement two real approval gates plus an atomic `claim_attempt_for_submit` compare-and-swap and an `outcome_unknown` state for crashes after the submit click that is never auto-retried. This is the best-engineered part of the codebase — the concern in the original draft of this document (that the two-gate design might not be real) does not hold up; it's real. |

**Retracted from the original document:** InterviewCoach, NLSearch, and LinkedInOutreach were listed as RC-4-affected on the strength of pattern inference. All three were confirmed, on direct read, to fail honestly instead. Their remaining problem is pure RC-2 (schema not sent → avoidable parse failures → visible `status:"failed"`), which is a worse user experience than silent success but not a trust violation.

---

# Part 2 — Fix Order

| Step | Change | Effort | Unblocks |
|---|---|---|---|
| 1 | `--force-recreate scheduler temporal-worker` | 2 min | JobSearch, FollowUp, EmailMonitor |
| 2 | Concurrency gate drops `awaiting_approval` | 1 line | every `/agents/run` agent |
| 3 | `echo=settings.DEBUG` | 1 line | ability to see anything |
| 4 | Schema + fence-strip in `call_llm_json` | ~15 lines | Resume, CoverLetter, JobSearch, FollowUp |
| 5 | `EMBEDDING_PROVIDER` setting + upload warning | ~30 lines | RAG for all agents |
| 6 | Worker fails loudly on missing secret; `/internal/health` boot check | ~10 lines | prevents RC-1 recurrence |
| 7 | `recover_expired_tasks` covers `AgentRun` + 48 h approval expiry | ~20 lines | RC-5, RC-6 permanently |
| 8 | Degraded-result flag; delete fabricated fallback text | ~40 lines | honest failure reporting |
| 9 | Migrate 6 hand-rolled JSON parsers to `call_llm_json` (also extracts the one shared `_strip_fences` helper, killing 4 copy-pasted copies) | ~200 lines | InterviewCoach×2, InterviewPrep, NLSearch, Salary, AutoApply's cold-email/note generators |
| 10 | `status:"error"` → `"failed"` at `job_search.py:1971,1977` and `resume_agent.py:192` | 3 lines | fixes a second, RC-1-independent stuck-spinner cause |
| 11 | `resume/page.tsx`, `cover-letter/page.tsx`, `interview-prep/page.tsx` call `POST /agents/{run_id}/approve` on success | ~15 lines × 3 | stops these three pages from orphaning a row on every successful use |
| 12 | Delete `_run_agent_background`; `user_settings` into state; delete stale `__pycache__` `_v2` artifacts | cleanup | — |

Steps 1–3 take under 10 minutes and should be done before anything is re-tested, because **until step 2 lands every E2E test below will return 429 rather than the real error.**

---

# Part 3 — End-to-End Test Plan (all 15 agents + RAG)

## 3.0 Preconditions — run these first, in order

Nothing below is meaningful until all six pass.

```bash
# P1 — backend alive
curl -sf https://api.careercraftsai.me/health

# P2 — worker containers hold the CURRENT secret (RC-1)
docker inspect -f '{{.Name}} {{.State.StartedAt}}' \
  careercraft-isolated-scheduler-1 careercraft-isolated-agent-worker-1 \
  careercraft-isolated-temporal-worker-1
stat -c '%y %n' /opt/careercraft-secrets/backend.env
# every StartedAt MUST be newer than the env mtime

# P3 — internal auth works
docker logs --since 10m careercraft-isolated-scheduler-1 2>&1 | grep -c 403   # must be 0

# P4 — no stale approvals blocking the gate (RC-5)
curl -sf -H "Authorization: Bearer $TOKEN" \
  https://api.careercraftsai.me/api/v1/agents/runs?limit=50 \
  | jq '[.[] | select(.status=="awaiting_approval" or .status=="running")] | length'
# must be < 2

# P5 — an active model is configured and reachable
curl -sf -X POST -H "Authorization: Bearer $TOKEN" \
  https://api.careercraftsai.me/api/v1/users/me/models/test \
  -d '{"model_id":"<id>"}' -H 'Content-Type: application/json'

# P6 — the primary resume is actually embedded (RC-3)
curl -sf -H "Authorization: Bearer $TOKEN" \
  https://api.careercraftsai.me/api/v1/rag/documents?doc_type=resume \
  | jq '.[] | select(.is_primary) | {filename, embedded_at}'
# embedded_at MUST NOT be null
```

## 3.1 Pass criteria — apply to every agent test

A test passes only if **all** of these hold. The first three are what the current fallback behaviour defeats.

1. `AgentRun.status` reaches a terminal state (`completed` / `awaiting_approval`) — not `running`, not `failed`.
2. `result.warnings` contains **no** entry matching `/fallback|unavailable|degraded/i`.
3. The output contains user-specific content — a string from the user's actual resume, not the phrase `"Software professional focused on practical delivery"`.
4. `agent_runs.tokens_used > 0` — proves a real LLM call happened.
5. `agent_runs.duration_ms` is within the documented timeout (AGENTS.md § Timeouts).
6. Backend logs for the run window contain no `LLM JSON parse failed` and no `Vector retrieval failed`.

Check 6 is the highest-signal one. Run this after every test:

```bash
docker logs --since 5m careercraft-isolated-backend-1 2>&1 \
  | grep -iE 'parse failed|Vector retrieval failed|agent failed|Fallback' \
  | grep -vi sqlalchemy
# must be empty
```

## 3.2 Per-agent procedures

Set once:

```bash
API=https://api.careercraftsai.me/api/v1
H="Authorization: Bearer $TOKEN"
JSON="Content-Type: application/json"
JD='Senior Python Engineer. Required: FastAPI, PostgreSQL, Docker, AWS, LangGraph. 5+ years.'
```

---

### T0 — RAG (prerequisite for everything)

```bash
curl -sf -X POST -H "$H" $API/rag/upload \
  -F file=@fixtures/resume.pdf -F doc_type=resume -F is_primary=true | jq
```

| Check | Expected |
|---|---|
| HTTP | `201` |
| `embedded_at` | non-null ← **this is the RC-3 canary** |
| `warning` | null |
| `ats_score` (poll after 10 s via `/rag/documents/{id}/ats`) | 0–100, non-null |

Negative test: upload a scanned image-only PDF → `warning` must mention "Scanned or image-only PDF".

---

### T1 — Orchestrator (routing)

Not directly invokable; verified by T2–T15 each landing on the right node. One explicit test:

```bash
curl -s -X POST -H "$H" -H "$JSON" $API/agents/run \
  -d '{"task_type":"not_a_real_task","context":{}}'
```
Expected: `400`, detail names the valid task types. Must **not** be `500`.

---

### T2 — JobSearchAgent ⚠️ RC-1

```bash
RUN=$(curl -s -X POST -H "$H" -H "$JSON" $API/agents/run \
  -d '{"task_type":"job_search","context":{"search_query":"python engineer","location":"Remote","max_results":10}}' \
  | jq -r .run_id)
```

Then, in order:
1. Stream: `curl -N -H "$H" $API/agents/$RUN/stream` — must emit `thinking` within 5 s.
2. Scheduler log must show `run-job-search … status=200` (**not 403**).
3. Poll `$API/agents/runs/$RUN` until terminal, max 120 s.
4. `result.jobs` length ≥ 1; each job has `title`, `company`, `url`, `match_score` in 0–100.
5. `GET $API/jobs/applications?status=saved` returns the new rows.

**If step 2 shows 403 → RC-1 is not fixed. Stop; nothing downstream will pass.**

---

### T3 — NLSearchAgent

```bash
-d '{"task_type":"nl_job_search","context":{"query":"remote senior backend role at a climate startup, $150k+"}}'
```

| Check | Expected |
|---|---|
| Parsed query in `result` | `location≈"Remote"`, `salary_min≈150000`, seniority senior |
| Delegation | a JobSearch run follows; `result.jobs` populated |

Depends on **both** RC-1 and RC-2 (it hand-rolls `json.loads` at `nl_search_agent.py:86` with no error handling — a bad parse throws straight out).

---

### T4 — ResumeAgent ⚠️ RC-2, RC-3, RC-4

```bash
curl -s -X POST -H "$H" -H "$JSON" $API/resume/optimize \
  -d "{\"jd_text\":\"$JD\",\"tone\":\"professional\",\"template\":\"modern\"}" | jq
```

| Check | Expected | Currently |
|---|---|---|
| `resume_markdown` | contains a real employer name from the uploaded resume | ❌ boilerplate |
| `summary` | present, non-generic | ❌ "Fallback draft — live model call failed." |
| `ats_score` | 0–100, computed (`ATSService`, not self-graded) | ⚠️ 0 |
| `keywords_matched` | overlaps `FastAPI/PostgreSQL/Docker/AWS` | ❌ `[]` |
| `warnings` | empty | ❌ `["LLM unavailable; …"]` |
| `pdf_document_id` | non-null; `GET /resume/download/{id}` → PDF bytes | ⚠️ |
| Backend log | no `LLM JSON parse failed` | ❌ fires 1–2× per call |

Then verify the HITL gate: the run appears in `GET /agents/runs` as `awaiting_approval`, `POST /agents/{run}/approve {"approved":true}` → `200`, status → `completed`.

**And verify RC-5 is fixed:** immediately after, `POST /agents/run` for any task must **not** return 429.

---

### T5 — CoverLetterAgent ⚠️ RC-2

```bash
curl -s -X POST -H "$H" -H "$JSON" $API/cover-letter/generate \
  -d "{\"tone\":\"formal\",\"jd_text\":\"$JD\"}" | jq
```

| Check | Expected |
|---|---|
| `content` | non-null, 200–500 words, names the role |
| `tone` | `"formal"` |
| Extended thinking | `tokens_used` includes thinking budget (≤ 6000) |

Negative: empty `jd_text` → `400` (not 500, not a letter about nothing).

---

### T6 — LinkedInAgent ⚠️ RC-4

```bash
-d '{"task_type":"linkedin_optimize","context":{"target_role":"Senior Python Engineer"}}'
```

| Check | Expected | Currently |
|---|---|---|
| `headline` | ≤ 220 chars, role-specific | ❌ hardcoded `_HEADLINE_PROMPT` text |
| `about` | 3–5 paragraphs from resume facts | ❌ hardcoded |
| `bullets` | exactly 3, each ≤ 2 lines | ❌ hardcoded |
| `thinking` | **must not** be "Fallback draft used because live model call failed." | ❌ is exactly that |

That `thinking` string is the single fastest way to tell a real LinkedIn run from a fake one.

---

### T7 — LinkedInOutreachAgent

```bash
curl -s -X POST -H "$H" -H "$JSON" $API/linkedin/outreach/identify \
  -d '{"company_name":"Stripe","role_context":"Senior Python Engineer"}' | jq
```

| Check | Expected |
|---|---|
| `contacts` | ≥ 1, each with name + title + rationale |
| `drafts` | one per contact, ≤ 300 chars (LinkedIn InMail limit) |
| HITL | `GET /linkedin/outreach/queue` lists them; `POST /linkedin/outreach/{run_id}/approve` required before send |

**Never auto-send.** Confirm there is no code path from `identify` to a send.

---

### T8 — EmailAgent ⚠️ HITL-critical

```bash
curl -s -X POST -H "$H" -H "$JSON" $API/email/compose \
  -d '{"company":"Stripe","role":"Senior Python Engineer","recipient_email":"test@example.com"}' | jq
```

| Check | Expected |
|---|---|
| `subject`, `body` | present, reference the company/role |
| `thinking` | **not** the `_fallback_email` text |
| Status | `awaiting_approval` — never `completed` |
| Gmail | **no** message in Sent |

Then the gate:
- `POST /email/approve/{run_id} {"approved":true}` → message appears in Gmail Sent.
- `POST /email/approve/{run_id} {"approved":false}` → nothing sent, status `cancelled`.
- **Negative (must fail):** any attempt to send without going through `/email/approve/{id}` must be impossible. Grep the codebase for `GmailService.send` callers and confirm `send_approved_email` in `workflow_service.py` is the only one.

---

### T9 — EmailMonitorAgent ⚠️ RC-1

Scheduled every 6 h via the Node worker's `status-check`. Force it:

```bash
-d '{"task_type":"email_monitor","context":{}}'
```

| Check | Expected |
|---|---|
| Scheduler log | `status-check … 200` (not 403) |
| `result.threads` | recruiter replies since last run |
| Drafted replies | `awaiting_approval`, never auto-sent |

---

### T10 — FollowUpAgent ⚠️ RC-1

Not a graph node — `schedule_followups()` is called from `internal.py`. Test via the pipeline:

1. Create an application with `applied_at = now()`.
2. Confirm two BullMQ delayed jobs exist (day-5, day-12):
   ```bash
   docker exec careercraft-isolated-redis-1 redis-cli \
     ZRANGE bull:agent-queue:delayed 0 -1 WITHSCORES | head
   ```
3. Fast-forward: set `applied_at` back 5 days, trigger `followup-email`.
4. Draft created with `awaiting_approval` — **not sent**.
5. **Auto-cancel test:** insert a recruiter reply on the thread, re-trigger → the scheduled follow-up must be cancelled, not sent.

Step 5 is the one that actually matters and is the most likely to be broken; it is also the most embarrassing failure mode (following up after someone already replied).

---

### T11 — InterviewCoachAgent ⚠️ RC-2 (verified: fails honestly, does not fake success)

```bash
S=$(curl -s -X POST -H "$H" -H "$JSON" $API/interview/session/start \
  -d '{"role":"Senior Python Engineer","company":"Stripe","question_type":"behavioral"}')
SID=$(echo $S | jq -r .session_id)
QID=$(echo $S | jq -r .question.id)

curl -s -X POST -H "$H" -H "$JSON" $API/interview/session/$SID/answer \
  -d "{\"question_id\":\"$QID\",\"answer\":\"At my last role I led a migration of ... (60+ words)\"}" | jq
```

| Check | Expected |
|---|---|
| First question | role-specific, not from a hardcoded list |
| `feedback.score` | 0–10 for each of clarity / relevance / depth |
| `feedback.feedback` | references the actual answer text |
| Next question | adapts to the previous answer |
| After N answers | `summary` with `overall_score`, `strengths`, `improvements` |
| `GET /interview/session/{id}/summary` | matches |

Negative: 5-word answer → the frontend blocks at <10 words; the **backend** independently rejects with a clear word-count error (`interview_coach_agent.py:292-300`, confirmed by read) rather than 500ing — this validation is already correct.

`interview_coach_agent.py:212` and `:352` both `json.loads` with a `JSONDecodeError` catch that returns `status:"failed"` with `error:"Agent failed"` — confirmed on read, this agent does **not** have the RC-4 problem. Under RC-2 its realistic failure mode is a visible `failed` run, not a disguised fake success — annoying, not deceptive.

---

### T12 — InterviewPrepAgent ⚠️ RC-2, RC-4

```bash
-d '{"task_type":"interview_prep","context":{"role":"Senior Python Engineer","company":"Stripe"}}'
```

| Check | Expected | Currently |
|---|---|---|
| `questions` | ≥ 15, categorised (Technical / Behavioral / Company-Specific) | ⚠️ |
| Company-specific ones | mention Stripe specifics | ❌ likely `_fallback_prep` |
| `study_guide` | present | ⚠️ |
| Log | no `"Interview prep LLM returned invalid JSON … Using fallback"` | ❌ |

That log line at `interview_prep_agent.py:118` is the canary.

---

### T13 — CompanyResearchAgent

```bash
curl -s -X POST -H "$H" -H "$JSON" $API/company/research \
  -d '{"company_name":"Stripe"}' | jq
```

| Check | Expected |
|---|---|
| Sections | all five present: `culture`, `interview_process`, `financials`, `recent_news`, `key_people` |
| Sources | EXA citations attached |
| Cache | second call within 7 days returns from `company_intel` in <500 ms |
| `GET /company/Stripe/intel` | returns the cached row |

Negative: a company with no web presence → graceful partial result, not 500.

---

### T14 — SalaryAgent ⚠️ RC-2

```bash
curl -s -X POST -H "$H" -H "$JSON" $API/salary/report \
  -d '{"role":"Senior Python Engineer","location":"Bangalore","experience_years":5,"current_salary":2500000}' | jq
```

| Check | Expected |
|---|---|
| `percentiles` | p25 < p50 < p75 < p90, all plausible for the market |
| `total_comp` | base + bonus + equity breakdown |
| `negotiation_script` | references the supplied current salary |
| `report_id` | `GET /salary/report/{id}` returns the same |

`salary_agent.py:202` `json.loads(raw.strip())` with a `JSONDecodeError` catch — **confirmed on read**: the catch path constructs a hardcoded templated script (opening line, counter-offer at p75, two generic justifications) and returns it indistinguishably from an LLM-written one (RC-4-lite). Test: force a parse failure (e.g. point at a model known to ignore the "JSON only" instruction) and confirm the returned `justifications` don't literally contain the string `"reflecting the value I bring"` — if they do, you got the template, not a real script, with no signal in the response.

---

### T15 — AutoApplyPipeline ⚠️ 2 HITL gates, Temporal

**Use a throwaway job posting or a staging board. Do not submit a real application during testing.**

Entry point is `/jobs` → "Apply":

```bash
curl -s -X POST -H "$H" -H "$JSON" \
  $API/jobs/applications/$APP_ID/prepare-apply -d '{"live_browser":false}' | jq
```

Walk all 10 documented steps:

| Step | Verify |
|---|---|
| 1 `get_job_details` | full JD retrieved |
| 2 `ResumeAgent.tailor` | real tailored resume (not RC-4 fallback) |
| 3 `CoverLetterAgent` | letter generated |
| 4 `ATSService.score` | score computed |
| 5 **HITL #1** | status `awaiting_approval`; pipeline **halts**; nothing submitted |
| 6 `FormFillerService.fill` | fields populated; human-like delays present in the Playwright trace |
| 7 **HITL #2** | status `awaiting_approval` again; screenshot of the filled form available |
| 8 `BrowserControlService.submit` | only after the second approval |
| 9 `ApplicationsService.create` | row created, stage `applied` |
| 10 `FollowUpAgent.schedule` | two delayed BullMQ jobs enqueued |

**The mandatory negative test:** reject at HITL #1 and at HITL #2 separately. In both cases confirm **no submission occurred** on the target site. If either rejection still submits, stop all auto-apply work — that is a ToS and user-trust incident, not a bug.

Temporal path (`TEMPORAL_ENABLED=true`): confirm the workflow appears in the `careercraft-auto-apply` task queue and that the two approval signals are what advance it.

**Architecture note (confirmed by full read of `auto_apply_pipeline.py`, `workflow_service.py`, `application_workflow.py`):** the two-HITL-gate design in AGENTS.md is real, not aspirational. `continue_action`'s `auto_apply_approval` branch reserves an `ApplicationAttempt` row before creating any child run; `run_application_stage` fills the form and returns a `browser_review` checkpoint before ever clicking submit; `claim_attempt_for_submit` does an atomic `awaiting_approval → submitting` compare-and-swap so a double-approval or a race can't double-submit; and a crash after the click lands in `outcome_unknown` (`mark_attempt_outcome_unknown`), a state the system never auto-retries. This is the best-engineered part of the codebase — test it to confirm it still behaves this way, not because it's suspected broken.

---

## 3.3 Full-loop smoke test

The 60-minute version that exercises the whole product:

1. Upload resume → `embedded_at` non-null.
2. Configure model → test succeeds.
3. NL search "remote senior python role" → jobs returned and saved.
4. Pick one job → tailor resume → ATS ≥ 70 → approve → download PDF.
5. Generate cover letter → approve.
6. LinkedIn outreach for that company → approve one draft.
7. Compose recruiter email → approve → verify in Gmail Sent.
8. Company research on that company → 5 sections.
9. Salary report for that role → percentiles ordered.
10. Interview prep → ≥ 15 questions; coach session → 3 scored answers.
11. Auto-apply on a throwaway posting → reject at HITL #1 → confirm nothing submitted.
12. Dashboard reflects: applications count, avg match, follow-ups due — all real numbers.

Step 12 is the acceptance test for the whole thing. If the dashboard still shows placeholder keywords (UI-1), the loop isn't closed.

---

# Part 4 — UI Bugs and Fixes

Grouped by severity. File and line references are current as of this branch.

## Critical — functionality is fake or unreachable

### UI-1 — `/interview-prep` "Mock interview" is entirely fake
`frontend/src/app/(app)/interview-prep/page.tsx:84-211`

```tsx
const MOCK_INTERVIEW_QUESTIONS = [
  "Tell me about yourself.",
  "What's your greatest technical challenge you've overcome?",
  ...
];
```

`MockInterviewModal` never calls an API. It cycles 5 hardcoded questions, collects answers into local state, discards them, and ends with:

> "You answered 5 questions. **Connect the backend to get AI-powered feedback** on your responses."

Meanwhile the real InterviewCoachAgent is fully implemented and wired at `/interview`.

**Fix:** delete `MOCK_INTERVIEW_QUESTIONS`, `MockInterviewModal`, and the "20-minute mock interview" banner (lines 757-783). Replace both entry points (line 435, line 773) with `router.push('/interview?role=…&company=…')` carrying the current prep context. ~150 lines deleted, ~3 added.

### UI-2 — Dashboard renders placeholder keywords as if they were real
`frontend/src/app/(app)/dashboard/page.tsx:275-277`

```tsx
missingKeywords={resumeData?.missing_keywords ?? ["TypeScript", "AWS", "Docker", "CI/CD"]}
```

A user with no resume uploaded sees four confident keyword recommendations that were invented by a hardcoded array. This is the "dashboard shows placeholder instead of real data" issue from the stabilization plan — it is a literal hardcoded array, not a data-fetch problem.

**Fix:** `?? []`, and have `ResumeScoreCard` render an "Upload a resume to see keyword coverage" empty state when the list is empty and `ats_score` is null.

### UI-3 — Dashboard quick actions silently do nothing on error
`dashboard/page.tsx:163-169`

```tsx
const triggerAgent = async (taskType, ctx) => {
  const { data } = await apiClient.post("/agents/run", { task_type: taskType, context: ctx });
  ...
};
```

No try/catch. Under RC-5 every click returns 429 → unhandled promise rejection → **the button does nothing at all**, no toast, no console message the user will see. This is a large part of why "none of the agents work" feels total.

**Fix:**
```tsx
try { ... } catch (e) { toast.error(getApiErrorMessage(e, "Could not start agent")); }
```
`getApiErrorMessage` already exists in `lib/api.ts`. The dashboard is the **only** page with zero error handling (`err=0` across the file).

### UI-4 — Dashboard quick actions send empty context
`dashboard/page.tsx:103-108`

```tsx
{ label: "Search Jobs",      taskType: "job_search",       ctx: { query: "", location: "Remote" } },
{ label: "Optimize Resume",  taskType: "resume_optimize",  ctx: {} },
{ label: "Research Company", taskType: "company_research", ctx: {} },
```

- `job_search` sends `query: ""` — and the backend expects `search_query`, not `query` (compare `agents/page.tsx:70`). **Wrong key name.**
- `resume_optimize` with `{}` → no `jd_text` → the agent tailors against nothing.
- `company_research` with `{}` → no `company_name` → guaranteed failure.

**Fix:** these should not be one-click. Open a small modal collecting the one required field, or route to the relevant page (`/jobs`, `/resume`, `/company`) with focus on the input. Cheapest correct version: make them links, not agent triggers.

### UI-5 — FollowUp agent has no UI and a dead link points at it
`components/marketing/Footer.tsx:21` links to `/agents?focus=followup`.

- `agents/page.tsx:138` reads only the `run` param. `focus` is ignored.
- `follow_up` is not in the `AGENTS` array (correctly — it is not a graph node).

Result: the footer advertises a "Follow-up Agent" whose link lands on a page with no trace of it.

**Fix:** either build a follow-ups surface (the data exists — `followups_due` is already on the dashboard stats) or point the footer at `/applications`, where follow-up state belongs. Also add `?focus=` handling to `agents/page.tsx` so deep links from marketing select the right agent card.

### UI-6 — AutoApply, NLSearch and EmailMonitor are only reachable via a raw JSON textarea
`agents/page.tsx:67-81` — the `/agents` page presents a JSON context editor. For `auto_apply`, `nl_job_search` and `email_monitor` that is the **only** entry point outside of `/jobs` → "Apply".

Auto-apply is the product's headline feature and its discoverable path requires the user to hand-edit JSON.

**Fix:** NL search deserves a prominent search box on `/jobs` (the backend endpoint exists). Email monitor belongs as a toggle + "Check now" on `/email`. Auto-apply already has the `/jobs` → Apply path — make sure it is visually the primary action, and remove the JSON-only impression from `/agents` by pre-filling contexts from real user data rather than `"Target Company"` strings.

## High — errors are hidden from the user

### UI-7 — `/cover-letter` replaces every backend error with the same wrong message
`cover-letter/page.tsx:42-50`

```tsx
} else {
  toast.error("We couldn't generate a cover letter. Check your active AI model in Settings and try again.");
}
```

Under RC-2 the model settings are fine — the schema bug is the cause. The user is sent to Settings to fix something that isn't broken, three times in a row, and concludes the app is broken (correct) for the wrong reason.

This contradicts commit `eed51a4` ("surface real backend error instead of generic"), which fixed this pattern elsewhere but not here.

**Fix:** use `getApiErrorMessage(error, fallback)` as the other pages do. Keep the specific 400/504 branches — they are genuinely actionable.

### UI-8 — `/agents` swallows the 429 detail
`agents/page.tsx:157`

```tsx
onError: () => toast.error("Could not queue the agent. Check your context, model settings, and active-run limit."),
```

Three possible causes in one message, none confirmed. The backend's 429 detail says exactly which limit was hit.

**Fix:** `onError: (e) => toast.error(getApiErrorMessage(e, "Could not queue the agent"))`. When the status is 429, additionally offer a "Cancel pending runs" action — under RC-5 this is the only way out without DB access.

### UI-9 — `/interview` swallows both error paths
`interview/page.tsx:53,72` — `onError: () => toast.error('Failed to start session')` / `'Failed to submit answer'`. Same fix.

### UI-10 — Stuck `running` runs spin forever with no escape
RC-6 produces runs that never terminate. `lib/sse.ts` polls `/agents/runs/{id}` every 3 s indefinitely (106 polls observed for one run). There is no timeout, no "this run appears stuck" state, and no cancel button on the run panel.

**Fix (frontend half):** after `AGENT_TIMEOUTS[type] + 60s` of `running` with no SSE event, render "This run stopped responding" plus a Cancel button hitting `POST /agents/{id}/approve {"approved": false}`. The backend half is RC-6.

### UI-11 — No visible distinction between a real result and a fallback
RC-4 returns `awaiting_approval` with `warnings: ["LLM unavailable; showing extractive fallback."]`. **Correction after code audit:** `/resume` does surface `warnings` — `resume/page.tsx:525` does `if (data.warnings?.length) toast.warning(data.warnings[0])` — but only as a toast that disappears in a few seconds, with no persistent marker on the draft itself, and `/cover-letter`, `/linkedin`, `/email`, `/interview-prep` render nothing from `warnings` at all. `ApprovalModal.tsx` (the shared reviewer used by `/agents`, `/jobs`, `/linkedin`) never reads `action.warnings` in any of its per-type branches either — confirmed by reading the component fully.

**Fix:** render `warnings`/`result.warnings` as a persistent amber banner above the draft — in `ApprovalModal` once, and on `/resume`/`/cover-letter`/`/interview-prep`'s own inline review UI (see UI-1/RC-5 — these three don't use `ApprovalModal` at all). Once RC-4's `degraded` flag lands, branch on that: degraded results should not show an "Approve" button at all — they should show "Retry".

### UI-21 — `ApprovalModal` has no renderer for most agent output types
Confirmed by full read of `ApprovalModal.tsx` (RC-12). Handled: `send_email`, `resume_ready`, `linkedin_edits`, `cover_letter_review`, `search_confirmation`, `browser_input`/`browser_review`, `application_answers_required`. Unhandled, falls through to a raw `<pre>{JSON.stringify(...)}</pre>` block: `linkedin_outreach`, `salary_report_review`, `interview_prep`, `auto_apply_approval`, `review_application_draft`, `interview_session_started`, `answer_evaluation`. A user approving a LinkedIn outreach batch — real names, titles, and drafted message bodies — reviews it as an unformatted JSON blob.

**Fix:** add per-type render blocks for at least `linkedin_outreach` (contact cards + message text) and `salary_report_review` (percentile chart + script) — the two most content-heavy of the unhandled types. Longer term, replace the `actionType === "..."` chain with a `Record<string, Component>` map so an agent that ships a new output type without a matching reviewer is a visible gap in the map, not a silent JSON fallback.

### UI-22 — Resume/CoverLetter/InterviewPrep tell the user "done" while orphaning the run server-side
Confirmed by full read (RC-5). `resume/page.tsx`'s `optimizeMutation.onSuccess` shows `toast.success("Resume tailored!")` and never calls `/agents/{run_id}/approve` — same for `cover-letter/page.tsx` and `interview-prep/page.tsx`. The user has no way to know a DB row now sits in `awaiting_approval` forever, silently consuming one of their two concurrency slots.

**Fix:** see RC-5 fix #4 — call `/approve` in `onSuccess`, or redesign these three to show an explicit Approve action like `/agents` does.

### UI-12 — Upload succeeds visually when embedding failed
RC-3 returns `201` with `embedded_at: null`. `/resume` and `/onboarding` show the upload as complete. The user has no idea their document is invisible to every agent.

**Fix:** in the documents list, show a badge when `embedded_at === null`: "Not indexed — agents can't read this" + a "Re-index" button calling a new `POST /rag/documents/{id}/reindex`. The backend `warning` field is already plumbed through `DocumentResponse` and only needs populating (RC-3 fix #2).

## Medium — polish and consistency

### UI-13 — Wrong product name shipped in three places
`agents/page.tsx:204`, `linkedin/page.tsx:317`, `linkedin/outreach/page.tsx:56` all render `eyebrow="Finlytic AI Agent"`. This is a different product's name, visible to users on three screens.

**Fix:** replace with "CareerCraft AI". Consider a `PRODUCT_NAME` constant — three independent copies is how this happened.

### UI-14 — Settings uses different fonts/icons than the marketing site
Reported in `docs/superpowers/plans/2026-09-21-post-nango-stabilization.md` Task 4. Requires live browser comparison — do not guess CSS values. Root cause is almost certainly Settings using raw Tailwind classes instead of the shared theme tokens the marketing header uses.

### UI-15 — Dashboard shell: black background with a white toggle
Same source. The dashboard shell doesn't use the marketing site's theme-toggle pattern. Also requires live iteration.

### UI-16 — "Log out" placement on Account settings
`settings/account/page.tsx:521` places Log out inside the Danger zone block (header at line 442). The original report said it appeared "right after the profile form" — **this appears to already be fixed on this branch.** Verify visually before touching it.

### UI-17 — Pages with no loading state
`cover-letter`, `email`, `onboarding` have zero `isLoading`/`isPending` guards (`load=0`). `/cover-letter` compensates with a local `generating` flag and a shimmer, so it is fine in practice. `/email` (834 lines) and `/onboarding` (604 lines) need an audit — with a 30 s axios timeout and slow agent calls, a dead-looking button is the default experience.

### UI-18 — Pages with no empty state
`company`, `cover-letter`, `dashboard`, `interview`, `salary`, `settings/*` have no empty-state copy (`empty=0`). `/company` and `/salary` in particular render a blank panel before the first run with no indication of what to do.

**Fix:** the pattern already exists — `dashboard/page.tsx:314-318` has a good dashed-border empty state. Reuse it.

### UI-19 — `/agents` JSON context editor has no validation feedback
`agents/page.tsx:144` does `JSON.parse(contextText)` inside the mutation. Malformed JSON throws into `onError`, which shows the same generic three-cause toast as a 429. The user can't tell a typo from a server limit.

**Fix:** validate on change, show inline parse errors under the textarea, disable Run while invalid.

### UI-20 — `AGENTS.md` documents interview routes that don't exist
AGENTS.md says `POST /interview/session` and `POST /interview/answer`. Actual routes are `/interview/session/start` and `/interview/session/{session_id}/answer`. The frontend uses the correct ones; the docs are stale and will mislead the next person writing tests.

**Fix:** correct AGENTS.md.

---

# Part 5 — Per-Agent UI State Coverage

Every agent needs five UI states. Current coverage:

| Agent | Screen | Idle/empty | Loading | Streaming | Error | Degraded (RC-4) |
|---|---|---|---|---|---|---|
| Orchestrator | `/agents` | ✅ | ✅ | ✅ | ⚠️ generic (UI-8) | ❌ |
| JobSearch | `/jobs` | ✅ | ✅ | ⚠️ stuck spinner (UI-10) | ✅ | ❌ |
| NLSearch | — | ❌ no UI (UI-6) | — | — | — | ❌ |
| Resume | `/resume` | ✅ | ✅ | ✅ | ✅ | ❌ (UI-11) |
| CoverLetter | `/cover-letter` | ✅ | ✅ | n/a inline | ❌ wrong msg (UI-7) | ❌ |
| LinkedIn | `/linkedin` | ✅ | ✅ | ✅ | ✅ | ❌ (UI-11) |
| LinkedInOutreach | `/linkedin/outreach` | ✅ | ✅ | n/a | ⚠️ generic | ❌ |
| Email | `/email` | ✅ | ❌ (UI-17) | n/a | ✅ | ❌ |
| EmailMonitor | — | ❌ no UI (UI-6) | — | — | — | ❌ |
| FollowUp | — | ❌ no UI + dead link (UI-5) | — | — | — | ❌ |
| InterviewCoach | `/interview` | ❌ (UI-18) | ✅ | n/a | ⚠️ generic (UI-9) | ❌ |
| InterviewPrep | `/interview-prep` | ✅ | ✅ | ✅ | ✅ | ❌ (UI-11) |
| CompanyResearch | `/company` | ❌ (UI-18) | ✅ | n/a | ⚠️ generic | ❌ |
| Salary | `/salary` | ❌ (UI-18) | ✅ | n/a | ⚠️ generic | ❌ |
| AutoApply | `/jobs` → Apply | ✅ | ✅ | ✅ | ⚠️ generic | ❌ |
| RAG | `/resume`, `/onboarding` | ✅ | ✅ | n/a | ❌ silent (UI-12) | ❌ |

**"Degraded" is unimplemented everywhere** — that column is the whole of RC-4/UI-11 and is why a broken platform looked like a working one.

---

# Appendix — Production Evidence Index

| Claim | Command |
|---|---|
| Scheduler 403s | `docker logs --since 24h careercraft-isolated-scheduler-1 2>&1 \| grep 403` |
| Container vs secret age | `docker inspect -f '{{.State.StartedAt}}' <c>` + `stat -c '%y' /opt/careercraft-secrets/backend.env` |
| JSON parse failures | `docker logs --since 24h careercraft-isolated-backend-1 2>&1 \| grep 'LLM JSON parse failed'` |
| Ollama embedding failures | `... \| grep 'Vector retrieval failed'` |
| Fallback resumes returned as 200 | `... \| grep 'POST /api/v1/resume/optimize'` (3 × 200, same window as 5 parse failures) |
| Stuck run polled 106× | `... \| grep -c 'GET /api/v1/agents/runs/08826ac0-e737-469c-81b1-20fa8c9eac23'` |
| No structured-output mechanism | `rg 'model_json_schema\|with_structured_output\|JsonOutputParser\|PydanticOutputParser' backend/app` → 0 |
| `_run_agent_background` unused | `rg '_run_agent_background' backend/` → 1 definition, 0 calls |

Backend unit + security suites pass (**520 passed, 71 skipped**) — confirming these are integration and environment failures that unit tests structurally cannot catch. Two additions would have: a contract test asserting `call_llm_json` sends the schema, and a startup check that the worker's `INTERNAL_SECRET` authenticates.

---

## Audit completeness

As of 2026-09-22 all 15 agent modules (`orchestrator`, `job_search`, `nl_search_agent`, `resume_agent`, `cover_letter_agent`, `linkedin_agent`, `linkedin_outreach_agent`, `email_agent`, `email_monitor_agent`, `followup_agent`, `interview_coach_agent`, `interview_prep_agent`, `company_research_agent`, `salary_agent`, `auto_apply_pipeline`) plus `harness.py`, `base_agent.py`, `thinking.py`, `strategies.py`, `state.py`, `semantic_memory.py` have been read line-by-line, not grepped. Core frontend agent infrastructure (`lib/sse.ts`, `store/agentStore.ts`, `components/agents/ApprovalModal.tsx`) has also been read fully. Part 1.5 is the verified summary; every "confirmed on read" note above replaces an earlier inference.

Not yet read at full depth: the remaining large page components (`jobs/page.tsx` 1194 lines, `email/page.tsx` 834, `leads/page.tsx` 517, `onboarding/page.tsx` 604, `settings/*`) — these were covered by the metrics-based scan in Part 4 (error/loading/empty-state counts) plus targeted greps, not a full read. If you want the same full-read treatment applied there, say so and it's the next pass.

## Two things I did not do

1. **I did not recreate the production `scheduler`/`temporal-worker` containers.** That is a production write. Say the word and it's one command (RC-1 fix).
2. **I did not query the production database.** Tool policy blocked it, so the `agent_runs` / `workflow_tasks` counts above are inferred from access logs rather than read directly. If you want exact numbers of stuck and `awaiting_approval` rows, run the P4 preflight query yourself.
