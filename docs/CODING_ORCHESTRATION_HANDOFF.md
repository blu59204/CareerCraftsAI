# GPT-6 Astra / Muse Spark coding handoff

## Agent configuration

- Coordinator: `astra-orchestrator`, model `openai/gpt-6-astra`.
- Coding worker: `muse-coder`, model `opencode/muse-spark-1.3-contributor-free`.
- IDs verified using the installed `opencode models openai` and `opencode models opencode`.
- Quit and restart OpenCode to load these project agents in the interactive session.
- The coding worker uses `mode: all` so the coordinator can delegate to it and it
  can also be exercised with `opencode run --agent muse-coder`.

## User's active objective

Implement scalable isolated browser workflows and verify the application; push
the reviewed application to GitHub; deploy via `ssh oraclevm` without disrupting
existing applications; expose CareerCraft through a separate ngrok tunnel.

## Current implementation

New workflow files: `backend/app/services/workflow_service.py`,
`backend/app/workflow_worker.py`, `sandbox_service.py`, `application_workflow.py`,
`backend/app/api/v1/browser.py`, `frontend/src/components/agents/BrowserWorkspace.tsx`.

The generic run API now writes a PostgreSQL transactional outbox. A separate
Python BullMQ worker claims tasks. Approvals create durable continuation tasks.
The browser workflow performs deterministic known-field filling, resumes login
and missing-answer handoffs, binds final approval to a form fingerprint and
resume hash, and checks submission confirmation. It is not yet proven across
all real job portals. It uses an OpenSandbox lifecycle adapter and encrypted
account state. The container uses --no-sandbox for Chromium because nested
namespaces failed under Docker; its isolation boundary is the outer container.

## Verification already performed

- Windows baseline: 341 unit tests passed, 61 skipped before new tests.
- New workflow unit tests: 16 passed.
- Fresh backend image unit tests: 356 passed, 62 skipped (with test configuration
  and both migration directories mounted).
- Disposable PostgreSQL/Redis/Chromium integration tests: 5 passed, including
  duplicate delivery, resume, expired worker, ownership, changed-form rejection,
  and one successful controlled form submission.
- Frontend build passed before the latest UI changes; rerun it before publishing.
- New backend files have outstanding Ruff style findings to address.

## Local test infrastructure

Docker project `careercraft-workflow-tests`, file `docker-compose.test.yml`:
PostgreSQL 55439, Redis 56379, browser CDP 59222, all loopback-bound.
Image `careercraft-backend-verify:local` successfully builds and imports Browser Use.
Windows Python: `backend/.venv_win/Scripts/python.exe`.
Integration command: set `RUN_WORKFLOW_INTEGRATION=1`, then run
`pytest tests/integration/test_durable_workflows.py -q -p no:cacheprovider` from backend.

## Remote state: preserve existing workloads

Oracle host: `oraclevm`, hostname `chola-public`, ARM64, 2 CPUs, about 12 GB RAM.
Existing Chola services and ngrok/nginx were active when last checked. They use
8080–8085, 4040, and PostgreSQL 5432. Do not stop/restart/reconfigure them.

Docker and Compose were installed without upgrading existing packages; existing
application services remained active afterward.

CareerCraft secrets were transferred via encrypted SSH stdin into the NEW
directory `/opt/careercraft-secrets`, mode 0700, files 0600. Do not print contents.
The supplied ngrok token is there, not in Git. `careercraft-ngrok.service` is a
new transient systemd unit; it targets 127.0.0.1:18180 and has its inspector at
127.0.0.1:14041. Its allocated hostname is
`https://platinum-pastime-overdrive.ngrok-free.dev`.
This URL is NOT a verified working app yet: the application stack is not deployed.

Deployment definitions: `deploy/oracle/compose.yml`, `nginx.conf`,
`OpenSandbox.Dockerfile` (server 0.2.3), `sandbox.toml`. They use separate ports
18100, 18101, 18179, 18180, 18190. OpenSandbox image compatibility and live network
policy enforcement still require real verification. Production migration has
not been applied. Need set public frontend/CORS URLs and permitted Supabase
redirect URLs for the new hostname, without overwriting other applications.

## GitHub

Remote: `https://github.com/blu59204/CareerCraftsAI.git`.
Local branch `master` and `origin/master` have diverged substantially. Do not
force-push. Create a deployment branch from the tested checkout.

There are many pre-existing user changes and untracked files. Review and stage
only application/deployment source and relevant tests; exclude secrets, profiles,
scratch scripts, generated files, and unrelated tooling. No new commits or pushes
have been made in this task yet.

GitHub CLI portable executable is at
`C:/Users/badbo/AppData/Local/Temp/opencode/bin/gh.exe`.
`scripts/github_access.py` runs gh using the existing Git credential helper
without printing credentials. Verified repository WRITE permission. Set
`GH_EXECUTABLE` to the path above when using it.

## Remaining priorities

1. Have Muse finish scoped correctness/style/test work; Astra reviews it.
2. Check task locking, action idempotency, retry boundaries, session expiration,
   credential handling, and model/provider compatibility.
3. Run final backend/container/frontend checks, including actual OpenSandbox.
4. Review Git changes and secret scan, commit and push a deployment branch.
5. Deploy that revision on Oracle with isolated ports/resource limits.
6. Apply only required migrations after validation; verify database policies.
7. Test public authentication, pages, model configuration, uploads, agent execution,
   approvals, and browser takeover. Report unavailable integrations honestly.
8. Recheck all existing Chola services and the original ngrok tunnel.
