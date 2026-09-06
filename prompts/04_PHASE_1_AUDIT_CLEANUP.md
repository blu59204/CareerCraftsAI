# PHASE 1 — AUDIT, ORGANIZE, ARCHIVE (no feature work)

## Goal
A clean, understandable tree. Every file has a reason to exist. Duplicates resolved. Nothing deleted, only
archived. Output is a written inventory the human approves BEFORE any move happens.

## Step 1.1 — Generate the inventory (human runs these, pastes output to model)
  cd "D:\CareerCraft AI"
  git status --porcelain > _inventory_git.txt
  Get-ChildItem -Recurse -File -Exclude node_modules,.next,.venv,__pycache__ |
    Where-Object { $_.FullName -notmatch "node_modules|\.next|\.venv|__pycache__|\.git\\" } |
    Select-Object @{n="path";e={$_.FullName.Replace("D:\CareerCraft AI\","")}}, Length, LastWriteTime |
    Export-Csv _inventory_files.csv -NoTypeInformation
  Get-ChildItem backend\app\agents\*_v2.py | Select Name

## Step 1.2 — Classification prompt (paste inventory + this)
Classify EVERY path into exactly one bucket and output a markdown table `path | bucket | reason`:
  KEEP        — referenced by main.py / imports / package.json / compose / migrations
  ARCHIVE     — dead forks (applyos/), old status .txt files, screenshots, stale logs, motionsites prompt lib,
                superseded docs (AUTHENTICATION_MIGRATION_TODO.md, PLEASE_PROVIDE_INFO.md, CLERK_*.md),
                test_*.py at root, output/, .browser_data/
  DECIDE      — *_v2.py agents, agentSlice.ts, duplicate services, anything you are unsure about
  SECRET-RISK — any file that may contain keys (.env*, *.log with tokens, .browser_data cookies)
Do NOT propose moving anything in KEEP. For DECIDE, list what the v1 and v2 differ in (human will paste both).

## Step 1.3 — v1 vs v2 agent decision (one prompt PER pair, 9 times)
Paste backend/app/agents/<x>_agent.py AND <x>_agent_v2.py AND orchestrator.py TASK_ROUTES.
Answer:
  1. Which one does orchestrator.py actually import?
  2. Table of differences (functions added/removed/changed).
  3. Recommendation: KEEP_V1 | KEEP_V2 | MERGE (with the exact function list to port from v2 into v1).
  4. If MERGE: output the merged file as `<x>_agent.py` (complete). Archive the v2.
Rule: the file that the orchestrator imports keeps the canonical name `<x>_agent.py`. No `_v2` names survive.

## Step 1.4 — Frontend duplicates
Paste store/agentStore.ts, store/agentSlice.ts, and `grep -r "agentSlice" frontend/src`. Migrate every
importer to agentStore.ts, archive agentSlice.ts. Same for any duplicate components found in Step 1.2.

## Step 1.5 — Execute moves (human runs, from model's approved list)
  New-Item -ItemType Directory -Force _archive
  # for each ARCHIVE path:  git mv "<path>" "_archive/<path>"  (create parent dirs first)
  Add to .gitignore: *.log, *.err.log, .browser_data/, output/, _inventory_*.txt, _inventory_*.csv
VERIFY:
  cd backend; .venv\Scripts\python -c "import app.main"        → no ImportError
  .venv\Scripts\python -m pytest tests\unit -q                → same pass count as before Phase 1
  cd ..\frontend; npm run type-check                          → 0 errors
  cd ..\worker; npm run build                                 → 0 errors

## Step 1.6 — Target structure (the model should aim for this; print it at end of phase)
backend/app/
  agents/            one <name>_agent.py per agent + orchestrator.py, harness.py, base_agent.py, state.py
  agents/prompts/    one <name>_prompt.py per agent  (created in Phase 3)
  api/v1/            one router per domain
  core/              config, database, security, auth, model_router, event_bus, redis_client, rate_limit
  services/          pure I/O helpers, no LLM prompt text inside
  models/            SQLAlchemy only
  schemas/           Pydantic request/response models (create if missing; move inline schemas here over time)
  tools/             LangChain tool wrappers used by agents
tests/unit tests/security tests/integration tests/e2e
frontend/src/{app,components,lib,store,hooks,types}
_archive/            everything else, mirrored paths, never imported

## PHASE 1 EXIT
[ ] inventory table approved by human
[ ] no *_v2.py, no agentSlice.ts, no duplicate llm_gateway
[ ] imports + tests + type-check pass
[ ] commit: "chore: archive dead files, merge v2 agents, resolve duplicates"
