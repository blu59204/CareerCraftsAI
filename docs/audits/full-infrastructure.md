# Full infrastructure and extension audit

Snapshot: `3a27b1c`. All 171 assigned tracked authored text files were read in full, including inactive runnable validation snapshots in `docs/agent-a` and `docs/agent-b` and six backend build/dependency/test configurations. Four extension icon binaries are inventoried separately; backend/requirements.lock is classified as generated dependency resolution. Coverage records byte SHA-256 and text line count in `coverage-infrastructure.csv`. Generated logs, third-party dependencies, ignored local deployment secrets and live host configurations were not treated as application source. locustfile.py is included in the full-content review. Backend nonunit tests and authored fixtures have their own coverage CSV and report.

## Confirmed findings

Remediation: INF-1 now leaves unknown one-click Apply controls to manual operation; INF-2 commits migration SQL and its ledger in one transaction, including normalized outer BEGIN/COMMIT files; INF-3 adds the production app origin at every extension pairing boundary; INF-4 uses an explicit Compose file/project and rejects errors, empty output, missing services and unhealthy/stopped services. Deployment instructions now reference the shipped topology. Node fixtures and disposable PostgreSQL failure/retry tests verify the changes; the Compose-check shell fixture exercises seven outcomes.

### INF-1 — P1: generic Apply buttons can submit before approval

`extension/src/content/drivers.js:323–331` chooses a visible Apply control on an unrecognized portal when no application form is found. `clickThrough`, lines 339–350, clicks any non-navigating control automatically. It never calls `markSubmitting`, opens review or requests the popup approval. A signed-in portal whose standalone Apply button sends an application immediately therefore bypasses the mandatory HITL gate. The dedicated Naukri handler correctly recognizes this risk at lines 625–642; the generic path does not.

Safe proof: executed the actual generic driver under Node's `vm` with a synthetic document containing no forms and one visible `button[type=button]` labeled Apply. The button's simulated click increments a submission counter; `markSubmitting` increments an approval counter. Result: `{"oneClickApplySubmissions":1,"approvalChecks":0}`. No network call or real submission occurred.

Recommendation: generic entry controls with unknown side effects must require explicit human review before automated click, or be left for manual takeover. Retain automatic navigation only for proven non-submitting portal entry contracts. Add a one-click generic fixture that asserts zero submits without the trusted popup permit.

### INF-2 — P2: migration DDL and ledger records commit separately

`scripts/migrate.py:139–144` executes a migration and only afterward records it. `main`, line 169, opens an autocommit connection. A crash or ledger-write failure between these two statements leaves the schema changed but the filename unrecorded. Retrying reruns non-idempotent files such as `0036_application_attempts_temporal_columns.sql:4–5` and fails, blocking deployment. The advisory lock prevents concurrent runs but does not repair this crash window.

Safe proof: fresh disposable PostgreSQL 16 container, a temporary migration containing `CREATE TABLE audit_probe(id integer);`, and an injected exception in `_record`. After failure, the table existed and the ledger contained zero entries. Retry failed with `relation "audit_probe" already exists`. The disposable container was stopped and removed; production containers were untouched.

Recommendation: commit each migration and its ledger row atomically, accounting explicitly for the files that currently contain their own BEGIN/COMMIT. Add a failure-before-ledger regression against actual PostgreSQL.

### INF-3 — P2: fresh installations cannot auto-pair from the production app subdomain

`deploy/oracle-vm/nginx.conf:13` serves the authenticated deployment on `app.careercraftsai.me`. That origin is absent from `extension/manifest.json:31–35,62–66`, `extension/src/common.js:5–11`, and the bridge known-app allowlist at `extension/src/background.js:543–544`. On a fresh installation, no bridge is injected on that origin; even a delivered bridge pairing request is rejected unless already paired there. The advertised Connect-this-browser flow therefore cannot bootstrap from the app subdomain. Manual popup pairing with a connection code is a workaround.

Recommendation: add the verified app origin consistently to static permissions, bridge matches, shared static origins and the pairing origin allowlist. Test first-install bridge pairing on that hostname.

### INF-4 — P2: production validation reports success when Compose inspection fails

`scripts/validate_production.sh:108–110` discards `docker compose ps`/JSON errors into an empty string and interprets that as all containers healthy. Invoking the script from the documented repository root currently targets no tracked default compose file, so a missing configuration or stopped/empty stack can pass this check. Neither successful inspection nor at least one required service is verified. This makes deployment validation give false assurance about availability.

Recommendation: select the actual deployment compose file/project explicitly, propagate command/parse failures, assert required services exist and check each service's applicable running/health state.

## Architecture and security observations

- Production API, frontend, PostgreSQL, Temporal frontend/UI and gateway bindings are loopback scoped in the tracked Oracle configuration. Ollama binds a private IP and explicitly requires operator firewall restrictions. Live firewall and gitignored Redis/Nango configurations were not verified.
- Extension final-submit handling uses a trusted popup sender, user-trusted click, task/frame binding, current snapshot comparison, content/file digests and a replay guard. These controls are sound on paths that actually invoke the gate; INF-1 is an earlier path outside it.
- The computer relay authenticates backend requests, scopes child tokens with HMAC, validates supervisor addresses, serializes owner actions and persistent erasure tombstones, and rejects unsupported model operations. Supervisor purge checks ownership labels before deleting containers/volumes. The documented test sandbox still uses Chromium without its own sandbox; its README correctly records that production readiness requires a supported sandbox/stronger runtime.
- SQL migration history retains old browser tables under backend-only archival names. Rollback snapshots are inactive/manual and several explicitly destroy tables; they are not automatic deploy rollback machinery.
- The migration bootstrap deliberately lets the API connect as table owner, bypassing RLS; API ownership checks are therefore the primary isolation boundary. RLS policies on active user data and backend-only ledgers were inspected, including policy recreation and column renames.
- CI runs with read-only GitHub permissions and live tests only on manual dispatch. Frontend dependency audit remains non-blocking and legacy Python lint/format exclusions remain explicit. These existing limitations were already reported in the previous remediation and are not new findings here.
- Root README deployment commands refer to nonexistent default Compose/Nginx files; `HOW_TO_RESTART.md` still describes Supabase authentication and a `worker` service while the active system uses Clerk and `temporal-worker`. These are documentation drift, separate from runtime security findings.

## Validation limits

This was full-content static review of assigned tracked files, plus the two isolated reproductions described above. No real email/application was sent, no deployed host was altered, no provider credentials were printed, and no claim is made that runtime settings, external services or third-party images were exhaustively audited. Source was not edited during this audit.
