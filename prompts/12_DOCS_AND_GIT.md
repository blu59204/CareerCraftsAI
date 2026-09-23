# PHASE 7 — DOCS, GIT HYGIENE, DEPLOY CHECKLIST

## 7.1 Git — reconcile with remote (human runs; model only interprets output)
cd "D:\CareerCraft AI"
git fetch origin
git log --oneline origin/main -20; git log --oneline origin/master -20
git diff --stat origin/main...HEAD
Paste output to model with this question: "origin/main has N commits I don't have. Are they older versions of
files I've since rewritten, or new work? Recommend: rebase, merge --no-ff, or make my master the new main."
Default recommendation if remote commits are all older duplicates: create branch `rebuild`, push it,
open a PR to main, review, merge. NEVER force-push main/master.

## 7.2 Commit the dirty tree in logical groups (order matters — each must pass its own verify)
1. chore(archive): move dead files to _archive, gitignore logs/inventory
2. fix(infra): redis/env/event_bus/worker (Phase 0)
3. refactor(agents): merge v2 into v1, add prompts/ package (Phase 1 + 3 install)
4. feat(slice): resume end-to-end (Phase 2)
5. feat(<agent>): one commit per agent (Phase 3)
6. feat(ui/<route>): one per page (Phase 4)
7. test: fixtures + coverage gates (Phase 5)
8. perf/ops: one per item (Phase 6)
9. docs: this phase
Before each commit: git diff --cached | findstr /i "sk- api_key= secret= password= eyJ" → must be empty.

## 7.3 Docs to rewrite (one prompt each; paste the current file)
- README.md: real stack versions (Next 16.2.6, LangGraph 0.2.76), real test count, Windows + Linux run
  commands, "what works today" table (agent | status | page), remove marketing claims not yet true.
- HOW_TO_RESTART.md: PowerShell version (Get-Process/Stop-Process, Remove-Item .next, docker compose
  restart redis), Supabase auth (no Clerk), how to read the three *.err.log files.
- docs/AGENTS.md (new, allowed): one section per agent — task_type, context keys, OUTPUT_SCHEMA, HITL yes/no,
  services used, timeout, budget, test file, page. Generated from prompt files — keep in sync.
- docs/API.md: regenerate from /openapi.json (script: scripts/gen_api_docs.py).
- Archive: AUTHENTICATION_MIGRATION_TODO.md, PLEASE_PROVIDE_INFO.md, CLERK_*.md, *_SUMMARY.txt status files.
- CLAUDE.md / AGENTS.md at root: replace phase-history with a pointer to prompts/00_HOW_TO_START.md.

## 7.4 Pre-deploy checklist (all boxes before `docker compose up -d` on the VPS)
[ ] APP_ENV=production, LOG_LEVEL=INFO, ALLOWED_ORIGINS = exact https domain(s)
[ ] Supabase: Auth providers (google/github/linkedin_oidc) + redirect URLs; Gmail scopes; RLS verified with
    a second test user (cannot read first user's rows)
[ ] All 32 migrations applied: supabase db push; HNSW index present (\d langchain_pg_embedding)
[ ] Redis: requirepass set, noeviction, appendonly volume mounted
[ ] INTERNAL_SECRET rotated; Nginx blocks /internal and /admin (except basic-auth)
[ ] certbot cert issued; TLS 1.2/1.3 only; security headers present (curl -I)
[ ] /health 200 all ok from outside; SSE works through Nginx (proxy_buffering off, read timeout ≥ 300s)
[ ] GH secrets VPS_HOST/VPS_USER/VPS_SSH_KEY; ci.yml green on main; cd.yml dry run
[ ] Smoke: real account → resume slice → one HITL agent (email draft → approve) → BullBoard shows jobs
[ ] Rollback plan written: `docker compose down; git checkout <prev-tag>; docker compose up -d`; tag each deploy

## 7.5 Release tagging
git tag -a v0.1.0 -m "first working release: resume slice + N agents"; git push origin v0.1.0
