# Scalable agent sandbox: project review and implementation plan

Review date: 2026-09-09. Scope: current working tree, with emphasis on agent execution, browser login, applications, approvals, and horizontal scaling.

## Executive conclusion

CareerCraft AI has useful foundations: Next.js, FastAPI, LangGraph agents, BullMQ/Redis, user-configured models, Browser Use, per-user Chromium profile directories, and approval UI/API scaffolding. The reviewed execution path does **not yet provide a complete, durable, multi-tenant sandbox workflow**.

The recommendation is to retain the application and Browser Use, repair execution and approval semantics, then introduce a separate sandbox lifecycle service and horizontally scalable workers. Evaluate OpenSandbox for self-hosted sandbox infrastructure. E2B Desktop is a useful managed prototype option. Skyvern is a workflow/authentication reference or alternative browser engine.

This is a source review plus focused local checks, not a live deployment or third-party account test. Repository capabilities below are based on upstream documentation inspected during this review; compatibility with this project's pinned dependencies requires a spike.

## What is already present

| Capability | Current implementation | Assessment |
|---|---|---|
| Browser reasoning and actions | `backend/app/services/browser_control_service.py:392` creates a Browser Use agent | Present |
| Per-user login reuse | `.browser_data/<user_id>` is used as the persistent Chromium profile | Local profile separation, not an OS sandbox |
| LinkedIn credential entry | `linkedin_login()` fills credentials directly through Playwright | Good separation from the login LLM prompt; incomplete challenge handling |
| Browser observation | Browser screenshots/events and frontend `agentStore.ts` handling | Partial, not interactive remote takeover |
| Application preparation | `auto_apply_service.py` and `form_filler_service.py` | Present, with disconnected stages and weak outcome validation |
| Human review | Approval modal, status checks, ownership checks | Present scaffolding; continuation is incomplete |
| Background scheduling | BullMQ workers for search, follow-up, status checks, daily search | Present, but generic agent execution bypasses this queue |
| Agent memory/model selection | Harness, model router, LLM gateway | Present, with multiple inconsistent execution/model paths |

## Prioritized findings

### P0: repair before expanding automation

1. **Async graph nodes are called through the synchronous graph API.**
   - Evidence: all node runners are async in `backend/app/agents/orchestrator.py:148`; `backend/app/api/v1/agents.py:105` and `backend/app/agents/harness.py:216` call `orchestrator.invoke` in an executor.
   - Verification: a minimal graph with an async node, using the installed `.venv_win` LangGraph, raises `TypeError: No synchronous function provided ... invoke via the async API`.
   - Fix: use `ainvoke`/`astream` and move blocking synchronous agent work off the event loop. Unify API and scheduled execution through the same worker/harness entry point.

2. **Approval does not durably resume the generic workflow.**
   - Evidence: `backend/app/api/v1/agents.py:284` publishes an `approved` event and changes status to `running`. It does not invoke a continuation or enqueue a resume job. The reviewed backend has no consumer executing `apply_browser` actions. `orchestrator.py:202` compiles without a checkpointer, and every node ends at `END`.
   - Additional mismatch: `_auto_apply_wrapper` at `orchestrator.py:65` always returns `completed`, even when the pipeline result requires approval. The approval endpoint rejects runs not in `awaiting_approval`.
   - Fix: persist each pending action and stage, use durable graph interrupts/checkpoints or a durable application state machine, and atomically enqueue a continuation after approval. Preserve both document review and completed-form review.
   - Dedicated email/LinkedIn approval endpoints exist; they do not repair this generic browser-application continuation path.

3. **The reviewed browser execution has no enforced submission authorization boundary.**
   - Evidence: `form_filler_service.py:239` switches prompt text according to `submit`; `browser_control_service.py:464` creates a general Browser Use agent without an application-level approval-aware tool policy.
   - Consequence: `submit=False` tells the model to stop but is not an independent technical prohibition on clicking a submit control.
   - Fix: separate preparation and submission capabilities. Bind authorization to the user, run, target, document hashes, and reviewed answers. Use controlled portal submit adapters and restrict generic write actions; unknown portals should hand final submission to the user until their action boundary can be enforced.

4. **Login credentials can enter the generic run record.**
   - Evidence: `RunRequest.context` is unrestricted; `agents.py:187` persists the entire context as run input. `orchestrator.py:73` accepts `context.linkedin_credentials`, which the pipeline expects to contain email/password.
   - Fix: reject credential fields on generic run requests. Use a dedicated credential/session connection flow; pass an opaque credential reference to workers. Scrub credentials from run inputs, model messages, traces, and screenshots. Direct Playwright entry alone does not address persistence in the upstream request path.

### P1: sandbox and login lifecycle

5. **Browsers run alongside the API, without per-workflow runtime isolation.**
   - Evidence: `browser_control_service.py:429` launches Chromium locally; `docker-compose.yml:20` runs this in the backend service. No sandbox provisioner is wired into this path.
   - Fix: provision a separate browser container or stronger sandbox per active workflow, with bounded CPU/RAM/processes, scoped files, and network policy. Keep database/admin credentials outside browser workloads. The sandbox manager, not the model, holds infrastructure provisioning authority.

6. **Browser state is destroyed at the point it needs to remain reviewable.**
   - Evidence: `run_browser_task()` always calls `browser.kill()` in `finally` (`browser_control_service.py:497`). Login closes its context at line 562.
   - Consequence: cookies may survive locally, but an in-progress form, tabs, or challenge cannot be assumed to survive or be available to the user.
   - Fix: lease a live browser through fill/review/submit. Use a bounded review TTL; if the lease expires, re-prepare and require review of the reconstructed form. Persist cookies separately from ephemeral runtime state.

7. **No complete interactive login, OTP, or account-creation handoff.**
   - Evidence: LinkedIn login returns a manual-review string for a checkpoint, but `auto_apply_pipeline.py:164-165` sets `linkedin_ready=True` whenever the helper returns without raising. Generic forms stop for OTP/account creation. No interactive remote input path was found in the reviewed frontend.
   - Fix: explicit `login_required`, `challenge_required`, `authenticated`, and `expired` states; an authenticated browser viewer with input takeover; pause agent input during takeover; verify the logged-in account before resuming.

8. **Profile persistence and concurrency are unsuitable for replicas.**
   - Evidence: profiles use a relative local directory. Production Compose mounts debug screenshots, not `.browser_data`. The semaphore at `browser_control_service.py:36` is process-local, and login does not use it. Two workflows can launch against the same user profile directory.
   - Fix: shared encrypted session storage and a distributed lease per user/platform/account. Restore into a workflow-private profile and persist back under an exclusive account lease. Enforce global, tenant, and platform capacity centrally.

### P1/P2: correctness, reliability, and maintainability

9. **Form outcomes can report success when blocked.** `form_filler_service.py:255-259` recognizes only `REQUIRES_MANUAL`, then labels every other returned string ready/applied. `REQUIRES_ACCOUNT_CREATION` is requested by its own prompt but not parsed. `browser_control_service.py:477` substitutes `Task completed` when no final result exists. Use structured results and verified page evidence; unknown outcomes must stay unknown/failed.

10. **The tailored document is not carried into the queued browser action.** `auto_apply_pipeline.py:265` stores a boolean for resume tailoring; the action at line 297 carries job URL/company/role but no approved document reference. Add an immutable artifact manifest, stage files into the sandbox, and verify the uploaded document matches the approved version.

11. **Form profile defaults can misrepresent the candidate.** `form_filler_service.py:65-68` defaults missing experience toward mid-level; `FORM_FILLER_SYSTEM` includes work-authorization defaults without corresponding verified profile fields. Required factual answers must come from confirmed candidate data, with missing answers sent to the user.

12. **CAPTCHA retry implementation does not match its comments.** `browser_control_service.py:122` retries with the same user/profile arguments; the alleged fresh profile suffix is not passed. The `solution` returned at line 139 is unused. Treat challenges as explicit workflow outcomes with user takeover rather than reporting retries as a complete solution. Do not blindly retry writes whose outcome may be unknown.

13. **Generic runs are process-bound and concurrency checks race.** `agents.py:193` uses `asyncio.create_task`; active-run counting is separate from inserting the new run. API restarts can lose execution, and concurrent requests can exceed the limit. Queue jobs durably, claim capacity atomically, and use worker leases/heartbeats. Timeout of an executor future does not guarantee the underlying work stopped.

14. **Progress delivery is ephemeral.** `backend/app/core/event_bus.py:98` uses Redis Pub/Sub; disconnected clients miss events. Persist ordered run events and support replay/cursors. Approval state must be recoverable from the database, independent of SSE delivery.

15. **Model handling diverges.** Browser Use builds its own provider clients, the pipeline imports `_build_llm`, and a separate `llm_gateway.py` exists. Browser fallback treats otherwise-unhandled providers as standard OpenAI, unlike the gateway's explicit OpenRouter/OpenCode URLs. Provide one model-resolution contract with engine-specific adapters and verified usage accounting.

16. **Existing test counts do not establish workflow readiness.** Several HITL tests inspect source strings/default arguments, while API tests mock the orchestrator. Add behavioral tests for actual async graph execution, resume after restart, interactive login, state retention, double approval, ambiguous submission results, and cross-user isolation.

## Scalable target architecture

```text
Next.js dashboard / authenticated browser viewer
                       |
              Stateless FastAPI replicas
                       |
        Durable run/action records + transactional outbox
                       |
           Redis/BullMQ admission and work queues
                       |
       +---------------+----------------+
       |                                |
 General agent workers          Browser workflow workers
 (LLM/research/documents)        (lease, heartbeat, checkpoints)
                                        |
                               Sandbox lifecycle service
                                        |
                          Isolated browser per active workflow
                          Chromium + scoped files + viewer
                                        |
                             Approved portal/domain access

Shared services: model gateway, encrypted session store, artifact storage,
durable graph checkpoints, ordered run events, metrics/traces.
```

### Design rules for horizontal scaling

- **Scale by active work, not registered users.** Allocate browsers on demand and cap paused/live-review sessions. Thousands of accounts do not require thousands of continuously running desktops.
- **Use separate worker pools.** Browser crashes and memory spikes must not consume API or document-generation capacity. Autoscale on queue age, active leases, CPU/RAM, and provider quotas.
- **Make admission distributed.** Combine global browser limits, per-user active-run limits, per-account exclusive session leases, and per-platform rate limits. Local semaphores remain only a secondary guard.
- **Treat processing as at-least-once.** Use idempotent stage transitions and unique action IDs. For external submissions, persist an intent before sending and reconcile confirmation evidence afterward. Unknown outcomes require reconciliation rather than blind resubmission; a third-party website cannot be assumed to provide exactly-once semantics.
- **Use an outbox for approved actions.** Approval, action state, and an outbox entry should commit together; the dispatcher safely retries queue publication. A Redis event alone is not a durable command.
- **Persist checkpoints, not just summaries.** Store the next stage, approved artifact versions, form snapshot, session reference, action state, and confirmation evidence. Persist state before emitting its UI event.
- **Manage browser leases explicitly.** Heartbeat, idle timeout, maximum lifetime, cancellation, orphan cleanup, and crash recovery belong to the lifecycle service. A paused form retains a bounded live lease; expired forms require reconstruction and fresh review.
- **Protect remote access.** Authorize viewer and control connections against the owning user/run. Use short-lived access tickets; keep CDP/VNC endpoints private. Pause automated input while a person has control.
- **Bound data and network access.** Mount only the required application files. Enforce egress rules and block internal infrastructure addresses. Encrypt session data at rest and restore only into the owning account's leased sandbox.
- **Persist tenant ownership everywhere.** Runs, sessions, artifacts, actions, and events must carry ownership and server-side checks; exposed database/storage access must enforce matching ownership policies.
- **Plan capacity from measurements.** Initial browser slots are bounded by the minimum of memory capacity, measured CPU capacity, provider quotas, and configured account/platform limits. Measure p95 working-set RAM and task latency on realistic forms; do not promise a user count from generic browser memory estimates.

### Recommended workflow

```text
queued -> provisioning -> session_check
  -> login_required / challenge_required -> user_takeover -> session_check
  -> prepare_documents -> awaiting_document_approval
  -> fill_form -> awaiting_form_approval
  -> authorized_submit -> verify_submission -> completed

Every stage can produce: cancelled, expired, failed, needs_input,
or unknown_submission_outcome requiring reconciliation.
```

Site account creation is a separate supported workflow only where implemented. It must expose required user inputs and verification steps rather than being silently counted as application success.

## Repositories worth using

| Repository | What it contributes | Recommendation |
|---|---|---|
| [browser-use/browser-use](https://github.com/browser-use/browser-use) | Existing Python browser agent, custom tools, browser profiles, job-application example | Retain; add the missing lifecycle and policy layer around it. MIT per upstream README. |
| [opensandbox-group/OpenSandbox](https://github.com/opensandbox-group/OpenSandbox) | Sandbox lifecycle APIs, Python/TS SDKs, Docker/Kubernetes runtimes, egress controls; Chrome example exposes VNC and DevTools | Best self-hosted infrastructure candidate for this project. Apache-2.0. Stronger isolation depends on the selected/configured runtime. |
| [e2b-dev/desktop](https://github.com/e2b-dev/desktop) | Isolated desktop template, Python/JS usage examples, authenticated interactive streaming | Useful for a managed prototype of login/takeover. Repository license is Apache-2.0; hosted usage is a separate service. SDK source has moved into [e2b-dev/E2B](https://github.com/e2b-dev/E2B). |
| [skyvern-ai/skyvern](https://github.com/skyvern-ai/skyvern) | Browser workflows, credential integration, documented 2FA support, form filling, validation, livestreaming | Strong reference or alternative engine, but a larger integration change. Core is AGPL-3.0; documented cloud-only features should not be assumed available self-hosted. |

OpenSandbox's [Chrome example](https://github.com/opensandbox-group/OpenSandbox/tree/main/examples/chrome) is particularly relevant: provision a browser with DevTools access for automation and VNC for human intervention. Browser Use's [job application example](https://github.com/browser-use/browser-use/blob/main/examples/use-cases/apply_to_job.py) is a useful artifact-upload reference. Neither replaces CareerCraft's durable approvals, tenant authorization, or outcome verification.

## Implementation sequence and acceptance criteria

### Phase 1 — execution correctness

- Unify worker entry points; fix async invocation; separate blocking operations.
- Implement durable pending actions, two approval stages, outbox-based resume, and idempotency.
- Use structured browser outcomes and immutable approved document references.
- Reject raw credentials in generic run input; correct missing-fact handling.
- **Acceptance:** a controlled application fixture completes prepare -> approve documents -> fill -> approve form -> submit -> verify. Double approval cannot create a duplicate action; no submit occurs before final authorization; process restart resumes the correct stage.

### Phase 2 — one real isolated browser workflow

- Introduce `SandboxProvider`/`BrowserSessionManager` interfaces with create, connect, lease renewal, destroy, and artifact transfer operations.
- Integrate an OpenSandbox Chrome proof of concept through a private remote browser connection.
- Add authenticated interactive viewing, login/OTP takeover, and session verification.
- **Acceptance:** two users cannot access each other's browser/session/files; challenge takeover resumes the same live form; cancellation and expiry release the sandbox; a required resume is actually uploaded and verified.

### Phase 3 — horizontal scaling and recovery

- Add shared account leases, bounded queue admission, worker heartbeats, autoscaling metrics, session persistence, and orphan cleanup.
- Add event replay and action reconciliation after ambiguous network failures.
- **Acceptance:** run a staged 1/5/20 concurrent-browser benchmark on known infrastructure; record queue wait, completion rate, p95 latency/RAM, model cost, and sandbox leaks. Repeat with a killed worker and API replica restart. Increase concurrency only when the measured budgets hold.

### Phase 4 — portal coverage

- Start with one or two controlled ATS flows, then broaden to real supported portals.
- Add verified account-state detection, factual field schemas, upload checks, and submission receipts for each supported flow.
- **Acceptance:** publish observed per-portal completion/manual-intervention rates and regression fixtures. Claim support from measured outcomes rather than a generic prompt accepting any URL.

## Checks performed

- Read the active browser/pipeline/form services, orchestration/harness/API paths, event bus, approval UI/store, worker entry point, container configuration, and relevant tests.
- Ran: `.venv_win\Scripts\python.exe -m pytest tests/unit/test_auto_apply_pipeline.py tests/unit/test_hitl_flow.py tests/unit/test_agents_api.py -q -p no:cacheprovider` from `backend`.
- Result: **19 passed**, with a pytest warning that the configured `timeout` option is unknown in this environment.
- Separately reproduced the synchronous-invocation failure using a minimal async-node graph with installed LangGraph. This reproduction did not invoke any external job portal or account.
- Read upstream repository documentation and the OpenSandbox Chrome example. GitHub CLI was unavailable, so public source documents were fetched over HTTPS.
- Production load, live database policies, actual sandbox deployment, and end-to-end third-party login/submission remain unverified.
