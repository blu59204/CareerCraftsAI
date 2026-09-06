# HARD RULES — paste after context in every prompt. Violating any = output rejected.

## Output format (mandatory)
1. Start with "PLAN:" — max 5 bullet points of what you will change and why.
2. Then for EACH file: a heading `### path/to/file.ext` followed by ONE code block with the COMPLETE new
   file contents (not a diff, not "..." placeholders, not "rest unchanged"). If a file is >300 lines and you
   only change one function, output the heading, then `REPLACE FUNCTION <name> WITH:` and the full function.
3. End with "VERIFY:" — the exact PowerShell commands to run and what output proves success.
4. End with "RISKS:" — anything you were unsure about, files you needed but were not given.
No prose between files. No apologies. No summaries of what the code does.

## Never
- Never invent a file, function, class, env var, or import that was not shown to you. If you need one, say so
  under RISKS and stop.
- Never hardcode a model name (e.g. "gpt-4o", "claude-3"). Always `await get_llm(user_id, db, task_type)`.
- Never send an email or submit an application without `_hitl_checkpoint()`. Never add a bypass flag.
- Never store or log an API key, JWT, or password in plaintext. Use core/security.py encrypt/decrypt.
- Never use CORS "*". Never auto-redirect on 401 in the frontend.
- Never lower browser delays in config.py (LinkedIn/Naukri detection).
- Never emit an SSE event type other than the six allowed.
- Never write to agent_runs except via the existing repository/helper functions.
- Never `git push --force`. Never commit .env.
- Never delete a file — move it to `_archive/` with the same relative path. Deletion is a human decision.
- Never create new markdown docs unless the task asks for it.
- Never change a function signature that other files call without listing every caller under PLAN.

## Always
- Python: type hints, `from __future__ import annotations`, async def for I/O, black + ruff clean, py312.
- TypeScript: strict, no `any` unless justified in a comment, named exports, `@/` imports.
- Wrap every external call (LLM, HTTP, browser, Redis) in try/except and return the error shape
  `{"status":"error","error": str(e)}` — never let an agent raise into the orchestrator.
- Emit `thinking` before slow work, `tool_call`/`tool_result` around every tool, `complete` or `error` at the end.
- Read `settings.X` from core/config.py; do not call `os.getenv` in agents/services.
- Every new endpoint: depends on `get_current_user`, uses `get_db`, returns a Pydantic model, has a rate limit.
- Every new agent function: accepts `state: AgentState`, returns partial AgentState dict, logs to agent_runs.
- Keep responses small: if the task needs >4 files changed, STOP and propose splitting it into sub-tasks.

## Environment facts
- Windows 11 + PowerShell 5.1. Use `;` not `&&`. Paths with spaces need quotes.
- Python venv: backend\.venv\Scripts\python.exe
- Tests: cd backend; .venv\Scripts\python -m pytest tests\unit -v
- Lint: cd backend; .venv\Scripts\python -m ruff check .; .venv\Scripts\python -m black --check .
- Frontend: cd frontend; npm run type-check; npm run lint; npm run build
