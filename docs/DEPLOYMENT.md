# Deployment Guide

Production runs on a single self-hosted Oracle Cloud "Always Free" ARM VM.
There is no Supabase Cloud dependency anywhere in this setup — Postgres,
auth verification, and everything else self-hosted or reached via each
service's own API (Clerk, the user's own AI provider, etc.).

---

## Infrastructure Overview

```
Internet
    │
    ▼
ngrok tunnel (configure_runtime.py + a systemd unit set this up;
              forwards to 127.0.0.1:18180)
    │
    ▼
Oracle Cloud "Always Free" ARM VM  (network_mode: host throughout —
                                     the VM has no IPv6 route, and
                                     Supabase's managed Postgres/Storage
                                     were IPv6-only from here)
├── gateway (nginx, loopback :18180)
│     /api/v1/* → backend :18100
│     everything else → frontend :18101
├── careercraft-isolated  (deploy/oracle-vm/compose.yml)
│   ├── backend           (FastAPI, :18100)
│   ├── frontend           (Next.js, :18101)
│   ├── temporal-worker    (python -m app.temporal_worker — runs every workflow)
│   ├── postgres           (pgvector/pgvector:pg16, :18132 — self-hosted DB)
│   ├── redis              (SSE pub/sub, rate limiting, LLM sessions — no queues)
│   └── sandbox-server     (OpenSandbox — isolated browser execution)
├── nango-isolated  (deploy/oracle-vm/nango-compose.yml)
│   └── self-hosted Nango — Gmail/Drive OAuth broker, :191xx range
└── temporal-isolated  (deploy/oracle-vm/temporal-compose.yml)
    └── self-hosted Temporal server + its own Postgres + Web UI,
        stock ports (7233 frontend, 6933–6939 cluster membership — the
        cluster-membership ports and temporal-postgres must never be
        reachable beyond loopback)
```

All three compose projects currently share this one VM "for now" — the
naming (`*-isolated`) anticipates splitting them onto separate boxes later
if load requires it; nothing about the current setup requires that split
today.

---

## Prerequisites

- An Oracle Cloud "Always Free" ARM VM (or equivalent — nothing here is
  Oracle-specific beyond the free-tier sizing and the lack of an IPv6 route)
- Docker + the Docker Compose plugin
- The `/opt/careercraft-secrets/` directory, containing (all gitignored,
  root-owned, `chmod 600`):
  - `backend.env` — `DATABASE_URL`, `REDIS_URL`, `CLERK_SECRET_KEY`,
    `APP_SECRET_KEY`, `TEMPORAL_ADDRESS` (+ `TEMPORAL_TLS_*` for mTLS),
    third-party API keys, etc. A leftover `INTERNAL_SECRET` is ignored.
  - `public.env` — `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`
    (frontend build args — see the note in `deploy/oracle-vm/compose.yml`
    about why these are passed as build `args`, not runtime env, and never
    merged into `backend.env`)
  - `postgres.env`, `redis.conf`, `sandbox.env`, `nango.env`, `temporal.env`
  - `ngrok.yml` — used by the systemd unit `configure_runtime.py` writes

---

## 1. Clone and check out the code

```bash
cd ~/CareerCraftsAI   # wherever the checkout lives on the VM
git checkout master
git pull origin master
```

---

## 2. Apply pending database migrations

There is no migration-runner wired up yet — migrations are applied by hand,
directly against the self-hosted Postgres, before deploying code that
depends on them:

```bash
sudo docker exec careercraft-isolated-postgres-1 \
  psql -p 18132 -U careercraft \
  -c "<the ALTER TABLE / CREATE ... from the new migration file in supabase/migrations/>"
```

Check `supabase/migrations/` for any file newer than what's already been
applied. This is a real gap worth closing eventually (a proper migration
runner, or at minimum a script that applies every unapplied file in order)
— tracked as follow-up work, not blocking day-to-day deploys.

---

## 3. Rebuild and restart the changed services

```bash
cd deploy/oracle-vm
sudo docker compose build backend frontend temporal-worker
sudo docker compose up -d backend frontend temporal-worker
```

Only rebuild the services whose code actually changed — rebuilding
`postgres`/`redis`/`gateway`/`sandbox-server` is never needed for an
application code change.

**Important:** `NEXT_PUBLIC_*` variables (the Clerk publishable key,
`NEXT_PUBLIC_API_URL`, etc.) are baked into the frontend's JS bundle at
**build time** via Docker build `args` — editing `/opt/careercraft-secrets/
public.env` and merely `docker restart`-ing the frontend container does
**not** pick up the change. A rebuild (`docker compose build frontend`) is
required whenever any `NEXT_PUBLIC_*` value changes.

---

## 4. Verify

```bash
sudo docker compose ps
curl -s http://127.0.0.1:18180/health | python3 -m json.tool
```

Expect `"status":"ok"`, `"db":"ok"`, `"redis":"ok"`, and
`"temporal":{"connected":true,"workers":<N>,...}`. A `workers` count of 0
means `temporal-worker` isn't actually registered even if the container
shows `Up` — `docker compose ps` alone doesn't catch that.

---

## Temporal (the only job engine)

Every agent run, job search, application, follow-up and recurring job is a
Temporal workflow; nothing else executes background work. To run it in
production:

1. **Server.** Bring up `deploy/oracle-vm/temporal-compose.yml` on its box
   (or use Temporal Cloud). Only port 7233 may be reachable from the app VM;
   6933–6939 and `temporal-postgres` stay on loopback.
2. **Transport security.** `TEMPORAL_ADDRESS` in `backend.env` must point at
   that server. If 7233 crosses a network the app VM doesn't own, set
   `TEMPORAL_TLS_CERT_PATH`/`TEMPORAL_TLS_KEY_PATH` (+ `TEMPORAL_TLS_CA_PATH`)
   and mount the files into `backend` and `temporal-worker`; without them the
   client connects in plaintext.
3. **Workers.** `temporal-worker` (task queue `careercraft`) is mandatory.
   `python -m app.notification_worker`
   (`deploy/oracle-vm/notification-worker-compose.yml`, task queues
   `careercraft-notifications*`) is required for in-app notifications and
   notification emails to be delivered.
4. **Schedules.** Each worker start registers `daily-job-search`,
   `maintenance` and, in `server_browser` apply mode only,
   `application-status-check` (`TEMPORAL_SCHEDULES_ENABLED=true`). Check with
   `temporal schedule list`.
5. **Retire the old queue workers** on any host that predates the Temporal
   migration: stop and remove the Node `worker` and Python `agent-worker`
   containers (`docker compose up -d --remove-orphans` does this for
   services no longer in the compose file), and delete the old queue's
   leftover Redis keys once no old worker is running. Redis stays — it backs the SSE
   event bus, the public demo's per-IP quota, LLM gateway sessions, token
   budgets and caches (slowapi limits are in-process).
6. **Verify** with `/health` (step 4 above) and, to run a job by hand,
   `temporal schedule trigger --schedule-id daily-job-search`.

---

## Ollama (embeddings)

Chat providers without an embeddings API (Anthropic, DeepSeek, OpenRouter,
NVIDIA NIM) index documents through a self-hosted Ollama serving
`qwen3-embedding:0.6b`. It runs on the Temporal box
(`deploy/oracle-vm/ollama-compose.yml`), bound to that box's private IP only —
Ollama has no authentication.

1. On the Temporal box, start it and pull the model:

   ```bash
   cd /opt/careercraft
   docker compose -f deploy/oracle-vm/ollama-compose.yml up -d
   docker compose -f deploy/oracle-vm/ollama-compose.yml exec ollama \
     ollama pull qwen3-embedding:0.6b
   ```

2. Allow TCP 11434 **only from the main app VM's private IP**, never
   `0.0.0.0/0`:
   - OCI: add an ingress rule to the subnet's security list — source
     `<app-vm-private-ip>/32`, TCP, destination port 11434.
   - On the box itself:

     ```bash
     sudo iptables -I INPUT -p tcp --dport 11434 -s <app-vm-private-ip> -j ACCEPT
     sudo iptables -A INPUT -p tcp --dport 11434 -j DROP
     sudo netfilter-persistent save
     ```

3. In `/opt/careercraft-secrets/backend.env` on the main VM:

   ```
   EMBEDDING_PROVIDER=ollama
   EMBEDDING_OLLAMA_URL=http://10.0.0.182:11434
   ```

4. Recreate the services that read it:

   ```bash
   docker compose -f deploy/oracle-vm/compose.yml up -d --force-recreate backend temporal-worker
   ```

5. Check from the main VM:
   `curl -s http://10.0.0.182:11434/api/tags` should list `qwen3-embedding:0.6b`.

After any embedding-model or dimension change, existing documents stay in
their old collection (collections are named `{user}_{doc}_{provider}_{dim}d`)
and are no longer searched. **Users must re-upload their documents** to
re-index them.

---

## Secrets rotation (e.g. switching Clerk from a development to a
## production instance)

1. Edit the relevant `.env` file under `/opt/careercraft-secrets/` directly
   (`sudo sed -i` or a text editor over SSH — these files are never in git)
2. Rebuild + restart whichever service reads that variable (see the
   `NEXT_PUBLIC_*` build-time note above — this is the most common way a
   key rotation silently fails to take effect)
3. Verify with a scoped, secret-safe check before trusting it, e.g.:
   ```bash
   sudo bash -c "grep -o '^NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=\"pk_[a-z]*' /opt/careercraft-secrets/public.env"
   ```

---

## Rollback

```bash
cd ~/CareerCraftsAI
git checkout <previous-commit-or-tag>
cd deploy/oracle-vm
sudo docker compose build backend frontend temporal-worker
sudo docker compose up -d backend frontend temporal-worker
```

There is no automated down-migration path — a schema change that needs
rolling back requires writing and running the inverse SQL by hand, the same
way the forward migration was applied in step 2 above.

---

## Known gaps (not yet solved, worth knowing about)

- **No CI/CD auto-deploy.** Deploys are manual (`git pull` + rebuild on the
  VM directly), not triggered by merging to `master`.
  `.github/workflows/cd.yml` still targets branch `main`, `/opt/jobagent`
  and the retired root `docker-compose.yml`; it does not deploy this stack.
- **No migration runner.** See step 2 above.
- **ngrok as the public ingress** is unusual for a permanent production
  setup (normally used for temporary/dev tunneling) — the comments in
  `deploy/oracle-vm/nango-compose.yml` describe the current one-VM layout as
  "for now," suggesting this is understood to be a transitional setup, not
  the intended long-term architecture.
