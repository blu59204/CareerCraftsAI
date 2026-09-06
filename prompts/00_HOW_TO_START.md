# HOW TO BUILD CAREERCRAFT AI WITH SMALL MODELS — START HERE

## The core rule
The app currently has ZERO working features. Do NOT try to fix everything.
Build ONE working vertical slice first, then add agents one at a time.
Every step must end with a command you run that proves it works.

## Recommended model roles (use whatever small models you have)
- BUILDER  : writes code for one narrow task (e.g. GPT-4o-mini / Haiku / Gemini Flash / Qwen-Coder 14-32B)
- REVIEWER : reads the builder's diff and finds bugs (a different small model, or same model in a fresh chat)
- TESTER   : writes/runs tests for the task
- ARCHITECT: (optional, one strong model call per phase) confirms the plan
Never use one long chat. Start a FRESH chat for every task. Paste context every time.

## How to assemble a prompt (every single time)
1. Paste 01_MASTER_CONTEXT.md (whole file)
2. Paste 02_RULES.md (whole file)
3. Paste the PHASE/TASK prompt you are on (e.g. 03_PHASE_0_ENV_FIX.md)
4. Paste the ACTUAL contents of the files the task lists under "READ THESE FILES"
   (open them in your editor and copy them — the small model cannot open your disk unless your tool lets it)
5. Send. Get output. Apply changes. Run the verification command.
6. Paste the builder's diff + verification output into a fresh chat with 10_REVIEWER.md
7. Fix what the reviewer finds. Re-run verification. Commit.

## Build order (do NOT skip or reorder)
PHASE 0  → 03_PHASE_0_ENV_FIX.md            Redis, env, worker green. Backend /health = ok.
PHASE 1  → 04_PHASE_1_AUDIT_CLEANUP.md      Inventory, archive junk, decide v1 vs v2, dedupe.
PHASE 2  → 05_PHASE_2_VERTICAL_SLICE.md     Login → add API key → upload resume → optimize resume → see SSE stream → download PDF. ONE path, fully working.
PHASE 3  → 06_AGENT_SYSTEM_PROMPTS.md       Install the 15 system prompts into backend/app/agents/prompts/
         → 07_PHASE_3_ONE_AGENT.md          Repeat once PER AGENT (15 times) in this order:
            resume → job_search → cover_letter → company_research → salary → linkedin →
            interview_prep → interview_coach → nl_search → email → followup → email_monitor →
            linkedin_outreach → auto_apply (last, hardest, 2 HITL checkpoints)
PHASE 4  → 08_PHASE_4_FRONTEND_WIRING.md    Repeat per page, wire to the now-working endpoints.
PHASE 5  → 09_TESTING.md                    Fill test gaps, fix count drift, CI green.
PHASE 6  → 11_SCALE_RELIABILITY.md          Timeouts, retries, HNSW, budgets, BullBoard, load test.
PHASE 7  → 12_DOCS_AND_GIT.md               Docs, git rebase, clean commits, deploy checklist.

## Definition of "done" for any task
- Verification command passes and you saw it pass
- Reviewer found no P0/P1 issues
- Committed with a message like: feat(resume): wire ResumeAgent end-to-end
- No secrets in the commit (git diff --cached | findstr /i "sk- key secret")

## Windows PowerShell reminders
- Chain commands with ;  not &&
- Backend tests: cd backend; .venv\Scripts\python -m pytest tests\unit -v
- Kill a port: Get-NetTCPConnection -LocalPort 8000 | % { Stop-Process -Id $_.OwningProcess -Force }
- Clear Next cache: Remove-Item -Recurse -Force frontend\.next

## When a small model gets stuck
- Shrink the task. Split into 2 prompts.
- Paste the exact error text and the exact 40 lines around it. Nothing else.
- Ask: "List 3 hypotheses ranked by likelihood, then give the fix for #1 only."
- If it invents a file/function that does not exist, reply: "That does not exist. Here is the real file: <paste>."
