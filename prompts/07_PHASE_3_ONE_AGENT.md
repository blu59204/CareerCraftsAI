# PHASE 3 — MAKE ONE AGENT WORK (repeat this file once per agent, fresh chat each time)

## Fill in before pasting
AGENT_NAME = <resume | job_search | cover_letter | company_research | salary | linkedin | interview_prep |
              interview_coach | nl_search | email | followup | email_monitor | linkedin_outreach | auto_apply>
TASK_TYPE  = <matching TASK_ROUTES key>
ENDPOINT   = <api/v1 file that exposes it>
PROMPT     = backend/app/agents/prompts/<AGENT_NAME>_prompt.py (installed in Phase 3 install step)

## READ THESE FILES (paste them)
- backend/app/agents/<AGENT_NAME>_agent.py
- backend/app/agents/prompts/<AGENT_NAME>_prompt.py
- backend/app/agents/base_agent.py, state.py
- backend/app/agents/orchestrator.py (TASK_ROUTES + _make_node_runner only)
- backend/app/api/v1/<ENDPOINT>.py
- backend/app/agents/resume_agent.py  ← the WORKING reference from Phase 2. Copy its shape exactly.
- Any services the agent imports (paste them)

## Step A — Contract check (model answers before coding)
1. Does <AGENT_NAME>_agent expose the callable that orchestrator TASK_ROUTES points to? Name it.
2. Which context keys does it require? List them. Which does the endpoint actually send?
3. Which external services does it call, and are they optional (degrade) or required?
4. Does it need HITL? (email, linkedin_outreach send, auto_apply submit → YES. All others → NO.)
5. What does `result` look like on success? Must equal the prompt's OUTPUT_SCHEMA dump.

## Step B — Rewrite the agent to the standard shape
```python
async def run_<agent_name>(state: AgentState) -> dict:
    run_id, user_id, ctx = state["run_id"], state["user_id"], state.get("context", {})
    try:
        await emit(run_id, "thinking", {"step": "start", "message": "..."} )
        # 1. validate ctx → missing keys → return {"status":"error","error":"missing: ..."}
        # 2. gather: rag_chunks / service calls, each wrapped: emit tool_call → call → emit tool_result
        # 3. llm = await get_llm(user_id, db, TASK_TYPE); messages = [System(SYSTEM_PROMPT), Human(build_user_prompt(ctx, chunks))]
        # 4. parse OUTPUT_SCHEMA with ONE retry on ValidationError
        # 5. persist domain row (cover_letter_versions / company_intel cache 7d / salary_reports / ...)
        # 6. if HITL needed: return await self._hitl_checkpoint(action_type, details)  (status awaiting_approval)
        # 7. await emit(run_id, "complete", {"result": result}); return {"status":"complete","result":result,"tokens_used":n}
    except Exception as e:
        await emit(run_id, "error", {"message": str(e)})
        return {"status": "error", "error": str(e)}
```
Rules: no prompt text in the agent; no hardcoded model; every external call try/except with a degraded path (e.g. Hunter missing → skip email finding, note in result.warnings).

## Step C — Endpoint
Endpoint validates a Pydantic request schema (put it in backend/app/schemas/<domain>.py), calls the same generic path as resume (POST /agents/run or harness) — do not invent a third pattern. Returns {run_id}.

## Step D — Unit test tests/unit/test_<agent_name>_agent.py
Mock get_llm to return a fake that outputs valid OUTPUT_SCHEMA JSON; mock services; assert: emits thinking first and complete last; result validates against OUTPUT_SCHEMA; missing ctx → error shape; LLM raising → error shape (no exception escapes); HITL agents → status awaiting_approval and redis pending set. VERIFY: cd backend; .venv\Scripts\python -m pytest tests\unit\test_<agent_name>_agent.py -v

## Step E — Manual check
POST /agents/run {task_type, context} with real key → stream → complete. Paste the SSE log if anything is off.

## Agent-specific notes
- job_search: search happens via services (jobspy / platform services), LLM only scores. Enqueue via BullMQ for >1 platform; inline allowed only when Redis unavailable in dev. Persist JobApplication(saved).
- company_research: check company_intel cache (7 days) BEFORE any search; cite sources by index.
- salary: pull data points from company_intel + search services; if <3 points, still return with low confidence.
- interview_coach: stateful per session (interview_sessions table); ASK and EVALUATE are two calls.
- nl_search: after parsing, call run_job_search with structured context — do not duplicate search logic.
- email / linkedin_outreach: ALWAYS end with _hitl_checkpoint("send_email"|"send_message", {draft...}). /approve then calls gmail_service / outreach service. Test that no send happens before approval.
- followup: not a graph node. schedule_followups(application_id) enqueues BullMQ delayed jobs (5d, 12d); processor calls /internal/run-followup → drafts → HITL → user approves in UI. Cancel when email_monitor labels a reply for that application.
- email_monitor: runs from status-check every 6h; writes action items; never sends.
- auto_apply: pipeline, not a single LLM call. Order: fetch JD → resume_optimize → cover_letter → ATS → CHECKPOINT 1 "review_documents" → browser fill via form_filler (auto_apply_prompt maps fields; any NEEDS_HUMAN → CHECKPOINT) → CHECKPOINT 2 "submit_application" → submit → JobApplication(applied) → schedule_followups(). Browser max_steps 25, human-like delays from settings, screenshot on every step to browser_debug when BROWSER_DEBUG_SCREENSHOTS. Resume the pipeline from redis agent:{run_id}:pending after each approval — never restart from step 1.

## PHASE 3 EXIT (per agent)
[ ] Step A contract answered and matches endpoint
[ ] unit test passes, no exception escapes the agent
[ ] manual run streams thinking → complete (or → checkpoint for HITL agents)
[ ] commit: "feat(<agent_name>): working end-to-end via orchestrator + tests"
