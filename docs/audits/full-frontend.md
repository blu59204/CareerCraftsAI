# Full frontend source audit — 2026-10-06

Scope: all 238 tracked frontend files at the audit checkout. Every authored text file was read in full, with oversized files split into contiguous ranges and truncated output re-read. `coverage-frontend.csv` records byte SHA256, line count, complete-read status and explicit exclusions. Binary PNG/MP4 assets, generated package lock and generated vendored Copilot stylesheet are excluded from manual code reading; its generator was read in full. No frontend source was changed by this audit. Complete reading does not imply absence of defects or production validation.

## Confirmed findings

### F-FE-01 — P1 — Account changes retain private cached results

`frontend/src/components/layout/Providers.tsx:17` constructs one QueryClient with five-minute freshness and ten-minute retention. It is mounted in the persistent root layout (`frontend/src/app/layout.tsx:113`) above the auth route groups. Sign-out handlers call Clerk signOut and client router navigation (`frontend/src/components/auth/UserMenu.tsx`, `frontend/src/app/(app)/settings/account/page.tsx:334`) without clearing caches. Keys such as `email-drafts`, `me`, `dashboard-stats`, `preferences`, `agent-memory` omit owner identity. In the same SPA lifetime, switching accounts can render the previous account's fresh private records without requesting the next account's data. A Node probe using installed QueryClient, configured with these defaults, populated `email-drafts` as account A then fetched the same key with B's queryFn: returned A's private body; B queryFn was never called. This verifies cache semantics; a live two-account Clerk browser flow was not run. Module-global agentStore also retains results/checkpoints, and persists `cc_active_run_id` without owner scope. Key the provider/store by authenticated owner or clear and abort on identity transitions; scope durable keys too.

### F-FE-02 — P1 — Approval preview differs from the message approved

`frontend/src/components/agents/ApprovalModal.tsx:129` submits editedText as body. The email, resume and cover-letter Edit/Preview controls set editing false while rendering original `action.body` or `action.resume_markdown` in preview (email around235–277, resume around330–359, letter around377–409). Thus Edit → change text → Preview → Approve reviews original content but submits changed content. Re-entering Edit resets the edited draft to the original; an empty edited body silently becomes no edits. Backend accepts body and maps it to resume_markdown where appropriate, so the field name itself is valid. Render the current edited content, track dirty state independently of truthiness, and validate emptiness before irreversible approval.

### F-FE-03 — P1 — Password recovery and common MFA sign-in paths are incomplete

`frontend/src/app/(auth)/login/page.tsx:483` supplies `onResetPassword={() => {}}`. `frontend/src/components/ui/sign-in.tsx:221` calls this from its reset form, labelled Send reset code, so no code or recovery operation occurs. Password sign-in handles needs_second_factor only when supportedSecondFactors contains email_code (login around263–282), while enrolled TOTP/backup/SMS second factors receive a generic additional-verification error with no way to supply their code. Wire Clerk password recovery and supported second-factor challenges. Separately account settings hardcodes twoFactor=false (`settings/account/page.tsx:214`, displayed988) even for an enrolled user; derive it from provider state.

### F-FE-04 — P2 — Terminal cancelled/expired runs remain live in generic stream UI

`frontend/src/lib/sse.ts:28` reconciliation handles completed/failed/queued/running/awaiting_approval, omitting cancelled and expired. SSE handlers also have no terminal cancelled/expired handling. Existing approval/checkpoint state consequently survives authoritative terminal status and keeps displaying pending action or running status. Jobs page has some separate reconciliation but agents/copilot generic stream remains affected. Use one exhaustive status transition layer, clear pending checkpoints on every terminal state and stop terminal polling. `agentStore.ts:147` also unconditionally deletes the persisted active marker whenever any old completed run reconciles, so a second run's restored marker can be lost.

### F-FE-05 — P2 — Assisted apply advances its queue on failed preparation

`frontend/src/components/agents/AutoApplyPanel.tsx:99` calls async startAssistedApply without awaiting its boolean success and immediately increments opened. The helper explicitly returns false on API failure. A failed item becomes counted as opened and next-click skips it; rapid clicks can queue overlapping preparations. Freeze target records, disable while preparing, and advance only on success with a retry path.

### F-FE-06 — P2 — Prep plan's mock launcher never evaluates or saves answers

`frontend/src/components/interview/PrepPlanPanel.tsx:683` promises live evaluated answers scored on clarity/structure/depth. Its MockInterviewModal at128 only accumulates local answers; completion210 says Connect the backend to get AI-powered feedback. Closing/unmounting loses those answers. The real API-backed MockInterviewPanel already exists on the same interview page's coach tab. Route the launcher there or reuse that session implementation.

### F-FE-07 — P2 — Email timeline shows fabricated sent/queued actions

`frontend/src/app/(app)/email/page.tsx:86` fixes follow-up steps to Day1 done, Day3 pending, Day7 upcoming. Its hero queued count710 is always2, and schedule995 always shows Sent/Queued, even with no drafts or Gmail connection. This conflicts with day5/day12 real followups and can make users believe outreach happened. Read actual draft/application workflow state or show a clearly labelled example without operational status.

### F-FE-08 — P2 — Google Sheets export silently ignores city filter

`frontend/src/app/(app)/applications/page.tsx:274` copies match/date/query/sort into export-sheet params but omits filters.location. List and CSV include location. Filter Bangalore then Export to Google Sheets exports other cities too. Include all supported active filters through one shared serializer.

### F-FE-09 — P2 — Jobs filter chips do not change their advertised criteria

`frontend/src/app/(app)/jobs/page.tsx:88` offers Job type, Experience level and Date posted chips; saved-list request around1331 consumes only location/mode chips. Search mutation around1640 uses profileForm.job_type/experience and postedDays instead of these selected chips. Changing Contract, Senior or Today leaves results/request unchanged. Map chips into supported request criteria or remove ineffective controls. View-all URL also drops location/source/status filters and replaces posted-time filtering with found-time filtering, so the linked count/list can differ.

### F-FE-10 — P2 — Lead created in the current page keeps stale status forever

`frontend/src/app/(app)/leads/page.tsx:624` gives localLeads precedence over fresh remoteLeads. Newly created leads remain in localLeads; statusMutation only invalidates remote query, never updates/removes local entry. Reaching out updates the server but row/detail/count remain Cold until reload. Store inserted lead in QueryClient or reconcile local entries on server updates.

### F-FE-11 — P2 — Discard salary script does not cancel its run

`frontend/src/app/(app)/salary/page.tsx` Discard handler near781 only toasts Script discarded. Report remains visible and underlying awaiting_approval run remains pending, counting toward concurrency and still approvable. Submit rejection through approval endpoint and reconcile the result.

### F-FE-12 — P2 — Fast notification toggles overwrite each other

`frontend/src/app/(app)/settings/account/page.tsx:203` builds each mutation with all five preferences from stale query values. Two toggles before invalidation/refetch send overlapping full snapshots; whichever resolves last undoes the other. Send only changed key or update/serialize optimistic state while requests run.

## Architecture and additional gaps

- Approval/status logic is duplicated among generic AgentStatusStream, Jobs, dashboard shortcuts, email, LinkedIn outreach and salary. Adopt shared typed status/approval contracts and reusable terminal transitions; test reviewed content against approved payload.
- React Query caches duplicate identical resources under models/user-models, resume-docs/rag-documents/dashboard-ats and several preferences keys. Mutations invalidate subsets, leaving stale summaries. Centralize query-key factories with owner scope and mutation invalidation.
- Several pages exceed800–1900 lines, interleaving network contracts, derived workflow state, dialogs and layout. Extract feature hooks/state transitions first, with behavioral tests, then presentational components.
- Handbuilt modal shells in PrepPlanPanel, Jobs and Leads declare aria-modal but lack focus trapping/restoration or inert background. Radix Dialog exists already. Shared Segmented advertises tabs/radio semantics without standard arrow/Home/End keyboard behavior or panel relationships. Test keyboard flows before claiming accessibility.
- AppTopbar's global search has no state or handler. CSV lead importer splits on commas rather than parsing quoted/multiline CSV; names/company fields with commas corrupt records. Account profile save sends blank optional fields as undefined, preventing clearing stored phone/headline/LinkedIn values.
- LinkedIn outreach Approve & Send is surfaced at `linkedin/outreach/page.tsx:239`; parent backend reviewer confirmed its legacy browser send service always raises, making approval fail. This cross-layer issue is owned by backend report.
- `frontend/package.json:11` test script runs only src/lib/*.test.mjs, omitting components/theme/theme-interactions.test.mjs. Add those regression tests to normal CI. No new full build/test-suite pass is claimed here.

## Verification limits

Static full-read audit plus installed QueryClient semantics probe. No real emails/applications were sent, no browser sessions or credentials were exercised, and no production configuration or live two-account/MFA session was tested. Cosmetic/marketing claims and legal validity were not independently verified. Generated dependencies and binary asset contents were explicitly excluded from line-by-line reading, rather than marked reviewed.
