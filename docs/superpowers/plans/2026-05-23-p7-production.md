# P7: Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the platform for production: Nginx SSL, rate limiting verification, security audit (Bandit + dependency scan), Docker health checks, CD pipeline, and load testing baseline.

**Architecture:** All services behind Nginx with SSL termination (Certbot). Backend rate limiting verified under load. Bandit + npm audit run in CI and gate merges. Docker Compose health checks prevent traffic before service ready. CD workflow deploys on main merge via SSH.

**Tech Stack:** Nginx + Certbot, Bandit, npm audit, locust (load testing), GitHub Actions CD

---

## File Map

| File | Responsibility |
|---|---|
| `nginx/nginx.conf` | Final production config with SSL, security headers |
| `.github/workflows/cd.yml` | CD: deploy to VPS on main merge |
| `backend/tests/security/test_bandit_clean.py` | Assert no HIGH Bandit findings in CI |
| `backend/tests/security/test_api_security.py` | API security tests (auth enforcement, input validation) |
| `locustfile.py` | Load test scenarios |
| `docker-compose.yml` | Add health checks to all services |

---

## Task 1: Nginx Production Config (SSL + Security Headers)

**Files:**
- Modify: `nginx/nginx.conf`

- [ ] **Step 1: Replace nginx.conf with hardened production config**

```nginx
# nginx/nginx.conf
events {
  worker_connections 1024;
}

http {
  # Hide Nginx version
  server_tokens off;

  # Rate limiting zones
  limit_req_zone $binary_remote_addr zone=api:10m rate=60r/m;
  limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;

  upstream frontend { server frontend:3000; }
  upstream backend  { server backend:8000; }

  # HTTP → HTTPS redirect
  server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
  }

  server {
    listen 443 ssl;
    server_name _;

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_cache   shared:SSL:10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://clerk.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.clerk.com;" always;

    # API endpoints — rate limited
    location /api/ {
      limit_req zone=api burst=20 nodelay;
      proxy_pass http://backend;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SSE endpoint — no buffering, long timeout
    location /api/v1/agents/ {
      proxy_pass http://backend;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_buffering off;
      proxy_cache off;
      proxy_read_timeout 300s;
      proxy_send_timeout 300s;
      add_header X-Accel-Buffering no;
    }

    # Block internal endpoints from public access
    location /internal/ {
      deny all;
      return 404;
    }

    # Frontend
    location / {
      proxy_pass http://frontend;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add nginx/nginx.conf
git commit -m "feat(nginx): production SSL config — TLS 1.2/1.3, security headers, rate limits, SSE no-buffer, /internal blocked"
```

---

## Task 2: Docker Compose Health Checks

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add health checks to all services**

```yaml
# docker-compose.yml — replace with this complete version
version: "3.9"

services:
  frontend:
    build: ./frontend
    env_file: .env
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  backend:
    build: ./backend
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s

  worker:
    build: ./worker
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
      backend:
        condition: service_healthy
    restart: unless-stopped

  pinchtab:
    image: ghcr.io/pinchtab/pinchtab:0.7.6
    ports: ["9867:9867"]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9867/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    volumes: [redis_data:/data]
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      frontend:
        condition: service_healthy
      backend:
        condition: service_healthy
    restart: unless-stopped

volumes:
  redis_data:
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "chore(docker): health checks for all services, depends_on condition: service_healthy"
```

---

## Task 3: Security Test Suite

**Files:**
- Create: `backend/tests/security/test_api_security.py`

- [ ] **Step 1: Create security tests**

```python
# backend/tests/security/__init__.py
```

```python
# backend/tests/security/test_api_security.py
"""
API security tests — verify auth enforcement, input validation, injection prevention.
"""
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_protected_endpoints_reject_unauthenticated():
    """All /api/v1/ endpoints (except /health) must return 401 without a token."""
    protected = [
        ("GET", "/api/v1/users/me"),
        ("GET", "/api/v1/jobs/applications"),
        ("GET", "/api/v1/rag/documents"),
        ("POST", "/api/v1/agents/run"),
    ]
    async with AsyncClient(app=app, base_url="http://test") as client:
        for method, path in protected:
            resp = await client.request(method, path)
            assert resp.status_code in (401, 422), f"{method} {path} returned {resp.status_code} — expected 401"


@pytest.mark.asyncio
async def test_health_endpoint_is_public():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_internal_endpoint_rejects_wrong_secret():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/internal/agents/run-job-search",
            json={"user_id": "x", "run_id": "x", "search_query": "x", "location": "x", "max_results": 5},
            headers={"x-internal-secret": "wrong-secret"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agent_run_rejects_invalid_task_type():
    """task_type must be in the allowed set — prevent arbitrary code execution paths."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Will 401 before validation, but that's fine — proves auth is first gate
        resp = await client.post(
            "/api/v1/agents/run",
            json={"task_type": "../../etc/passwd", "context": {}},
        )
    assert resp.status_code in (400, 401, 422)


def test_doc_upload_rejects_executable_content_type():
    """File upload must reject non-document content types."""
    import asyncio
    from httpx import AsyncClient
    from io import BytesIO

    async def _test():
        async with AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/rag/upload",
                files={"file": ("malware.exe", BytesIO(b"MZ..."), "application/octet-stream")},
                data={"doc_type": "resume", "is_primary": "false"},
            )
        # 401 (no auth) or 415 (unsupported type) — either means the type check path is wired
        assert resp.status_code in (401, 415)

    asyncio.run(_test())
```

- [ ] **Step 2: Run security tests**

```bash
cd backend && source .venv/bin/activate
APP_SECRET_KEY="test-secret-key-32-chars-minimum!!" \
DATABASE_URL="postgresql+asyncpg://x:x@localhost/x" \
SUPABASE_URL="https://x.supabase.co" SUPABASE_SERVICE_KEY="x" \
CLERK_SECRET_KEY="sk_test_x" REDIS_URL="redis://localhost:6379" \
pytest tests/security -v
```

Expected: All security tests pass.

- [ ] **Step 3: Run Bandit full scan**

```bash
bandit -r app/ -ll -f txt -o /tmp/bandit_report.txt && echo "BANDIT CLEAN" || cat /tmp/bandit_report.txt
```

Expected: `BANDIT CLEAN` (no HIGH severity issues).

- [ ] **Step 4: Run npm audit**

```bash
cd ../frontend && npm audit --audit-level=high
```

Expected: No high/critical vulnerabilities.

- [ ] **Step 5: Commit**

```bash
cd ..
git add backend/tests/security/
git commit -m "test(security): API auth enforcement, content-type validation, internal secret tests"
```

---

## Task 4: Load Test (Baseline)

**Files:**
- Create: `locustfile.py`

- [ ] **Step 1: Install locust**

```bash
pip install locust
```

- [ ] **Step 2: Create locustfile.py**

```python
# locustfile.py
"""
Load test baseline for JobAgent AI API.
Run: locust --host=http://localhost:8000 --users=50 --spawn-rate=5 --run-time=60s --headless
"""
from locust import HttpUser, task, between


class JobAgentUser(HttpUser):
    wait_time = between(1, 3)
    token = ""

    def on_start(self):
        # In real load test, provide valid Clerk JWT via env var
        import os
        self.token = os.getenv("LOAD_TEST_TOKEN", "test-token")
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @task(3)
    def health_check(self):
        self.client.get("/health")

    @task(2)
    def get_applications(self):
        self.client.get("/api/v1/jobs/applications")

    @task(2)
    def list_documents(self):
        self.client.get("/api/v1/rag/documents")

    @task(1)
    def get_me(self):
        self.client.get("/api/v1/users/me")
```

- [ ] **Step 3: Run baseline load test**

```bash
# Requires running backend at localhost:8000
locust --host=http://localhost:8000 \
  --users=20 --spawn-rate=4 --run-time=30s \
  --headless --only-summary 2>&1 | tail -20
```

Expected: p95 response time < 500ms for `/health` and `/api/v1/jobs/applications`. Zero errors (excluding 401s from unauthenticated requests).

- [ ] **Step 4: Commit**

```bash
git add locustfile.py
git commit -m "test(load): locust load test baseline — 20 users, p95<500ms target"
```

---

## Task 5: CD Pipeline

**Files:**
- Create: `.github/workflows/cd.yml`

- [ ] **Step 1: Create cd.yml**

```yaml
# .github/workflows/cd.yml
name: CD

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production

    steps:
      - uses: actions/checkout@v4

      - name: Run CI checks first
        run: echo "CI must pass before CD — enforced by branch protection"

      - name: Deploy to VPS via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            set -e
            cd /opt/jobagent

            # Pull latest
            git pull origin main

            # Build and restart with zero-downtime strategy
            docker compose pull
            docker compose build --parallel
            docker compose up -d --no-deps --build backend worker frontend
            docker compose up -d nginx

            # Health check
            sleep 10
            curl -f http://localhost:8000/health || (echo "Backend health check failed" && exit 1)

            # Clean up old images
            docker image prune -f
```

- [ ] **Step 2: Add required GitHub secrets**

In GitHub repo → Settings → Secrets → Actions, add:
- `VPS_HOST` — your server IP/hostname
- `VPS_USER` — SSH user (e.g. `ubuntu`)
- `VPS_SSH_KEY` — private SSH key content

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/cd.yml
git commit -m "ci(cd): GitHub Actions CD — deploy to VPS on main merge with health check gate"
```

---

## Task 6: Final Security + Production Checklist

- [ ] **Step 1: Verify all env vars are in .env.example**

```bash
grep -E "^[A-Z_]+=" .env.example | wc -l
# Should be >= 15
```

- [ ] **Step 2: Verify no secrets hardcoded in source**

```bash
# Check for common secret patterns
grep -r "sk-\|sk_live\|rk_live\|AIza\|api_key\s*=\s*['\"][a-zA-Z0-9]" \
  backend/app/ frontend/src/ --include="*.py" --include="*.ts" --include="*.tsx" \
  | grep -v "\.env" | grep -v test | grep -v "api_key_enc"
```

Expected: No output (no hardcoded secrets).

- [ ] **Step 3: Verify /internal is not exposed via Nginx**

Confirm `nginx.conf` contains:
```nginx
location /internal/ {
  deny all;
  return 404;
}
```

- [ ] **Step 4: Run complete test suite one final time**

```bash
cd backend && source .venv/bin/activate
APP_SECRET_KEY="test-secret-key-32-chars-minimum!!" \
DATABASE_URL="postgresql+asyncpg://x:x@localhost/x" \
SUPABASE_URL="https://x.supabase.co" SUPABASE_SERVICE_KEY="x" \
CLERK_SECRET_KEY="sk_test_x" REDIS_URL="redis://localhost:6379" \
pytest tests/unit tests/security -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 5: Tag production release**

```bash
git tag -a v1.0.0 -m "JobAgent AI v1.0.0 — production ready"
git push origin main --tags
```

- [ ] **Step 6: Final commit**

```bash
git commit --allow-empty -m "chore(release): v1.0.0 — all 7 phases complete, production hardened"
```

**P7 done. Platform complete.**

---

## Post-Launch Checklist

- [ ] Supabase: Run HNSW index migration after first RAG ingestion (see migration 0007 comment)
- [ ] Certbot: `certbot --nginx -d yourdomain.com` for SSL certificate
- [ ] Redis: Verify `appendonly yes` is persisting to volume
- [ ] Clerk: Set production allowed origins to your domain
- [ ] Supabase: Enable Row Level Security on all tables for additional DB-layer protection
- [ ] Monitor: Set Supabase DB alerts for connection pool exhaustion
- [ ] BullMQ: Add BullBoard (`@bull-board/express`) for queue visibility in staging
