# PHASE 4 — WIRE ONE PAGE (repeat per page, fresh chat each)

## Fill in
PAGE      = frontend/src/app/(app)/<route>/page.tsx
ENDPOINT  = POST /api/v1/<...>  (from Phase 3, already working via curl)
TASK_TYPE = <TASK_ROUTES key>
RESULT    = OUTPUT_SCHEMA fields from the matching prompt file (paste the schema)

## READ THESE FILES (paste)
- PAGE and every component it imports from components/
- lib/api.ts, lib/sse.ts, store/agentStore.ts, components/agents/{AgentStatusStream,ApprovalModal}.tsx
- app/(app)/resume/page.tsx ← the WORKING reference from Phase 2. Copy its pattern exactly.
- frontend/src/types/agents.ts (create if missing: one TS interface per OUTPUT_SCHEMA, keep in sync by hand)

## Standard page pattern (every agent page looks like this)
1. Form (react state or simple useState; zod optional) → validates required context keys client-side.
2. Submit → `const {data} = await apiClient.post(ENDPOINT, body)` → `agentStore.initRun(data.run_id, TASK_TYPE)`.
3. `useAgentStream(data.run_id)` → live <AgentStatusStream runId /> shows thinking/tool events.
4. `checkpoint` event → <ApprovalModal /> opens with details; Approve → POST /agents/{id}/approve
   {approved:true, edits?}; Reject → {approved:false}. Modal cannot be dismissed without a choice.
5. `complete` → render RESULT with typed components. LLM text always through lib/sanitize.ts.
6. `error` → toast (sonner) + "Retry" button (re-posts same body). No auto-redirect on 401; show
   "Session expired — Log in again" link.
7. Loading/empty/error states for every list. TanStack Query for GET lists (runs, applications, versions).
   Invalidate the query on `complete`.
8. Mobile: single column below md. Keyboard: form submits on Enter, modal focus-trapped.

## Per-page result renderers (build these components under components/<domain>/)
- jobs: JobMatchCard list sorted by score, red_flags badge, "Prepare apply" → auto_apply flow, Save → applications
- cover-letter: markdown preview + alternative_openings tabs + Copy + Save version + "Use in application"
- company: sections per schema field, sources list with [n] anchors, confidence bar, cached badge (7d)
- salary: p25/p50/p75/p90 bar, recommended_ask, negotiation script accordion, email_version copy
- linkedin: before/after diff per field, Copy each, character counters (220/2000)
- linkedin/outreach: queue table (linkedin_outreach_queue) + draft cards + ApprovalModal per send
- email: thread list (left) + draft (right) + ApprovalModal; action_required chip
- interview: chat UI; ASK → question bubble; EVALUATE → score chips (clarity/relevance/depth) + model_answer
- interview-prep: questions grouped by type, 5-day plan checklist, YouTube cards (i.ytimg.com thumbnails)
- applications: ApplicationKanban (saved → applied → interviewing → offer → rejected) + ApplicationDrawer
  showing followups scheduled and email_monitor items
- agents: run history table (GET /agents/runs) with status, duration, tokens; click → replay stream from
  agent_runs.output; remove the stale `// BUG n` comments
- dashboard: MetricCard x4 from aggregated stats endpoint, recent runs, action items from email_monitor
- settings/models: provider select, model select (list from backend), key input, Test key, budget field

## VERIFY (per page)
cd frontend; npm run type-check; npm run lint
Browser: full flow with DevTools → 0 console errors, 0 failed requests (except expected 4xx you handle),
network tab shows SSE frames, result renders, refresh preserves last completed result (from agent_runs).

## PHASE 4 EXIT (per page)
[ ] flow works in browser end-to-end
[ ] type-check + lint clean
[ ] commit: "feat(ui/<route>): wire <task_type> page to live agent stream"
