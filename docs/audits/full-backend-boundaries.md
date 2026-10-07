# Full backend boundary and architecture audit

Snapshot: `3a27b1ccd190c2b5f6950d5d9ddabd87ca1df342`. The 94 Python files in `coverage-backend-boundaries.csv` cover API routes, core, models, integrations, workflows, application adapters and worker entry points. Empty modules are explicitly classified. This supplements the services, frontend and infrastructure reviews.

## Confirmed findings

### BND-1 — P1: generated tailored resumes cannot enter application submission

`backend/app/applications/submission.py:35` accepts only `doc_type == "resume"`. `backend/app/agents/resume_agent.py:61` persists generated PDFs as `resume_tailored`. The queue's tailor-per-job path assigns that generated document to the application and the pipeline also loads its generated PDF through this helper. Both fail with `Approved resume is unavailable` before submission preparation. This breaks the default tailored application flow even when the artifact belongs to the user.

Proof: executed the actual `load_resume` with a mocked database returning an owned `resume_tailored` document. It raised the stated ValueError before storage access. This is an isolated contract reproduction, not a live portal test.

Recommendation: define the accepted resume artifact types in the responsible document/submission layer and reuse that contract throughout candidate selection and approval. Preserve ownership, size, PDF and approved snapshot checks. Cover both uploaded and generated PDFs.

### BND-2 — P2: deleting a referenced document fails at the database boundary

`backend/app/api/v1/rag.py:486–488` enqueues cleanup and deletes a document without clearing dependent references. `JobApplication.resume_id`, `JobApplication.cover_letter_id` and `CandidateProfile.default_resume_id` reference `user_documents` without an ON DELETE action that permits this deletion. The corresponding migrations retain those constraints. Deleting a document already used by an application or selected as the default therefore raises an integrity error; the transaction rolls back, including cleanup.

Evidence: full route/model/migration tracing. A live production deletion was not attempted.

Recommendation: explicitly define which historical application references must be preserved and which optional references can be nulled; implement that policy transactionally with matching foreign keys. Return a meaningful conflict where retention is required, rather than an unhandled server error.

### BND-3 — P2: dedicated agent endpoints bypass shared admission and execution invariants

`backend/app/api/v1/jobs.py:804–842` serializes duplicate searches but creates additional running searches for distinct inputs without calling `check_run_admission`. `email.py:175–224` directly executes an agent without shared admission or token/duration accounting; failures raise before transaction commit, losing the run record. `resume.py:150–222` also directly executes outside shared admission and durable workflow dispatch. Generic agent execution already owns these controls in `run_utils.py`, while dedicated paths duplicate only subsets. Users can exceed the documented two-run cap through these endpoints, and audit/recovery behavior depends on which endpoint they choose.

Recommendation: move dedicated routes onto the shared admission and durable dispatch boundary, preserving response compatibility. Test mixed endpoint concurrency and persisted failure/usage records, not only generic `/agents/run`.

### BND-4 — P1: tailored PDF writes can race account erasure

`backend/app/api/v1/resume.py:556` creates replacement storage while holding a document lock, without the owner lifecycle lock. Account cleanup sweeps external storage before database cascade. A replacement write after that sweep but before cascade can update and commit an existing document that the cascade then removes, leaving its new private PDF outside any document cleanup record. A document lock cannot protect the external sweep because cleanup reaches that lock only during later database deletion. This finding concerns replacement of an existing document; new document insertion also acquires an implicit owner foreign-key lock and compensates failed inserts, so the same race is not asserted for that path.

Evidence: concurrent ordering traced across the producer and account cleanup transaction. A disposable PostgreSQL 16 reproduction held an existing document lock, simulated the owner's external sweep, committed its replacement, then completed the owner cascade: zero document rows remained but `new.pdf` remained in the simulated file store. A separate new-row probe blocked on the owner's lock, failed with ForeignKeyViolation after deletion, and compensated its file. The disposable container was removed; no live account was erased.

Recommendation: reuse the owner lifecycle guard at every document-producing boundary, with the owner lock held across due-deletion validation and storage/database publication. Ensure failed storage compensation remains durable.

### BND-5 — P2: idle SSE streams poll Redis without a blocking timeout

`backend/app/core/event_bus.py:150–159` wraps `pubsub.get_message` in `wait_for(5)` but does not pass the Redis read timeout. The installed Redis default is a nonblocking poll returning None when idle. `wait_for` does not make an immediately completed call wait; the loop immediately polls again, generating unnecessary Redis traffic per open stream and skipping periodic idle keepalives.

Proof: actual `stream_events` with an immediate-None mocked PubSub produced 46,183 polls in 100 ms. A prior isolated probe also showed rapid polling. These numbers illustrate the loop behavior and are not a live Redis throughput benchmark.

Recommendation: use the native PubSub blocking timeout and yield a keepalive on idle expiry. Test idle poll count and timely cancellation with the installed Redis API.

### BND-6 — P2: approved LinkedIn outreach still calls retired automation

`backend/app/api/v1/linkedin.py:233` calls `linkedin_send_connection` after approval. That helper invokes `run_browser_task_with_captcha_retry`, whose underlying `run_browser_task` unconditionally raises because server browser task execution was retired. The frontend still presents Approve & Send. The reachable send feature therefore fails every time instead of providing a supported handoff. This is a functional contract failure; no successful send or exposed provider-key leak is asserted.

Recommendation: use a supported, explicitly reviewed user handoff or disable the send capability with an accurate explanation until a supported path exists. Keep HITL authorization at any future send boundary.

## Architecture assessment

The existing durable workflow, owner-scoped repositories, approval ledgers and cleanup outbox are useful foundations. Remaining failures cluster where older direct routes or artifact producers bypass those shared boundaries. Consolidation should target admission, owner lifecycle, artifact contracts and side-effect authorization rather than introducing more parallel service abstractions.

Database RLS is not the sole tenant boundary: the API database role owns tables. Every reachable API, worker and agent object lookup must consequently enforce owner identity, including generic dispatch paths. Dedicated route ownership checks cannot make a generic agent invocation safe.

The browser extension final-submit permit is carefully bound to reviewed content, but earlier entry clicks can still have irreversible effects. Side-effect classification must precede any automated click; final-submit correctness alone is insufficient.

## Limits

This report records static full-content review plus isolated mocked proofs. No deployed settings, provider accounts or real submissions were exercised. Prior passing test results apply to the previously remediated snapshot; no source edits were made during this full audit.
