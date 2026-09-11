# Deployment Guide

Production deployment uses Docker Compose on a VPS with Supabase Cloud for the managed data layer.

---

## Infrastructure Overview

```
Internet
    │ HTTPS (443)
    ▼
Ubuntu 22.04 VPS
├── Nginx (TLS termination, reverse proxy)
├── Docker Compose
│   ├── frontend (Next.js, port 3000)
│   ├── backend (FastAPI, port 8000)
│   ├── worker (BullMQ Node.js)
│   └── redis (port 6379)
│
└── Supabase Cloud (external)
    ├── PostgreSQL 16 + pgvector
    ├── Auth
    └── Storage
```

---

## Prerequisites

- Ubuntu 22.04 LTS VPS (minimum: 2 vCPU, 4GB RAM, 40GB SSD)
- Domain name pointed at the VPS IP
- Docker + Docker Compose installed
- Supabase project created (free tier works for dev/staging)

---

## 1. Initial Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose plugin
sudo apt install docker-compose-plugin

# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Install Supabase CLI
curl -fsSL https://github.com/supabase/cli/releases/latest/download/supabase_linux_amd64.tar.gz | tar xz
sudo mv supabase /usr/local/bin/
```

---

## 2. Clone and Configure

```bash
mkdir -p /opt/careercraft
cd /opt/careercraft
git clone https://github.com/blu59204/CareerCraftsAI.git .
cp .env.example .env
```

Edit `.env` with production values:

```bash
# App
APP_ENV=production
APP_SECRET_KEY=<openssl rand -hex 32>

# Supabase
DATABASE_URL=postgresql+asyncpg://postgres:[password]@db.[project].supabase.co:5432/postgres
SUPABASE_URL=https://[project].supabase.co
SUPABASE_SERVICE_KEY=<service_role key from Supabase dashboard>
NEXT_PUBLIC_SUPABASE_URL=https://[project].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key from Supabase dashboard>
SUPABASE_JWT_SECRET=<JWT secret from Supabase Settings → API>

# Redis (internal Docker network)
REDIS_URL=redis://redis:6379

# External APIs
HUNTER_API_KEY=<hunter.io>
PROXYCURL_API_KEY=<proxycurl>
EXA_API_KEY=<exa.ai>
RESEND_API_KEY=<resend.com>

# Frontend
NEXT_PUBLIC_APP_URL=https://yourdomain.com
NEXT_PUBLIC_API_URL=https://yourdomain.com/api
```

---

## 3. TLS Setup

```bash
# Obtain SSL certificate
certbot --nginx -d yourdomain.com --email your@email.com --agree-tos --non-interactive

# Update Nginx config with domain
sed -i 's/${DOMAIN}/yourdomain.com/g' nginx/nginx.conf
```

---

## 4. Run Database Migrations

```bash
supabase db push --db-url "$DATABASE_URL"
```

---

## 5. Start the Stack

```bash
# Build and start all services
docker compose up -d --build

# Verify all services are healthy
docker compose ps

# Check logs
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f worker
```

Expected output from `docker compose ps`:

```
NAME           STATUS          PORTS
frontend       Up (healthy)    3000/tcp
backend        Up (healthy)    8000/tcp
worker         Up              
redis          Up (healthy)    6379/tcp
nginx          Up              0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

---

## 6. Verify Health

```bash
# Backend health
curl https://yourdomain.com/health
# → {"status":"ok","version":"1.0.0"}

# Frontend
curl -s -o /dev/null -w "%{http_code}" https://yourdomain.com
# → 200
```

---

## 7. Configure Supabase Auth

In the Supabase dashboard (Authentication → Providers):

1. **Google OAuth**
   - Enable Google provider
   - Add `https://yourdomain.com/auth/callback` as allowed redirect URL
   - Required scopes: `email`, `profile`, `https://www.googleapis.com/auth/gmail.send`, `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/drive.readonly`

2. **GitHub OAuth**
   - Enable GitHub provider
   - Add `https://yourdomain.com/auth/callback` as allowed redirect URL

3. **LinkedIn (OIDC)**
   - Enable LinkedIn OIDC provider
   - Add `https://yourdomain.com/auth/callback` as allowed redirect URL

In Authentication → URL Configuration:
- Site URL: `https://yourdomain.com`
- Redirect URLs: `https://yourdomain.com/auth/callback`

---

## 8. Configure GitHub Actions CI/CD

Pushes to `main` auto-deploy via `.github/workflows/cd.yml`.

Add these secrets in GitHub → Settings → Secrets:

| Secret | Value |
|---|---|
| `VPS_HOST` | Your server IP or hostname |
| `VPS_USER` | SSH user (e.g. `ubuntu`) |
| `VPS_SSH_KEY` | Private key content (from `~/.ssh/id_rsa`) |
| `VPS_DEPLOY_PATH` | `/opt/careercraft` |

The CD workflow:
1. SSH into VPS
2. `git pull origin main`
3. `docker compose up -d --build`
4. `docker compose exec backend alembic upgrade head` (if migrations added)

---

## Docker Services Reference

### docker-compose.yml

```yaml
services:
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_SUPABASE_URL
      - NEXT_PUBLIC_SUPABASE_ANON_KEY
      - NEXT_PUBLIC_API_URL
    healthcheck:
      test: wget -qO- http://localhost:3000/health || exit 1
      interval: 30s

  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [redis]
    healthcheck:
      test: python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
      interval: 30s

  worker:
    build: ./worker
    env_file: .env
    depends_on: [redis]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: [redis_data:/data]
    command: redis-server --appendonly yes
    healthcheck:
      test: redis-cli ping
      interval: 10s

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on: [frontend, backend]
```

---

## Nginx Configuration

Key Nginx behaviors:

```nginx
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=api:10m rate=60r/m;
limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;

# SSE proxy (no buffering, long timeout)
location ~* /api/v1/agents/.*/stream {
    proxy_pass http://backend;
    proxy_buffering off;
    proxy_read_timeout 300s;
    proxy_set_header Connection '';
    chunked_transfer_encoding on;
}

# Block internal routes
location /internal/ {
    return 404;
}

# Security headers
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
add_header X-Frame-Options DENY always;
add_header X-Content-Type-Options nosniff always;
add_header Content-Security-Policy "default-src 'self' ..." always;
```

---

## Production Checklist

Before going live:

- [ ] `APP_ENV=production` set (disables `/docs` and debug logging)
- [ ] `APP_SECRET_KEY` is 32+ random bytes (generated with `openssl rand -hex 32`)
- [ ] Supabase Auth redirect URLs include your production domain
- [ ] Google OAuth scopes include `gmail.send`, `gmail.readonly`, `drive.readonly`
- [ ] Redis `appendonly yes` enabled (data persists across restarts)
- [ ] HNSW index migration run after first document upload
- [ ] SSL certificate auto-renewal configured: `certbot renew --dry-run`
- [ ] Supabase connection pool size set appropriately (10–20 for small deployments)
- [ ] GitHub Actions secrets set for CI/CD

---

## Monitoring

```bash
# Service status
docker compose ps

# Real-time logs
docker compose logs -f backend

# Redis queue depth
docker compose exec redis redis-cli llen bull:job-search:wait

# Disk usage
df -h

# Container resource usage
docker stats
```

---

## Scaling

For higher load:

1. **Backend:** Increase uvicorn workers: `CMD uvicorn app.main:app --workers 4`
2. **Worker:** Increase BullMQ concurrency in `worker/src/index.ts` (default: 2 per user)
3. **Redis:** Move to managed Redis (Upstash, Redis Cloud) for persistence + clustering
4. **Database:** Upgrade Supabase plan for higher connection limits and read replicas
5. **Browser Use:** Run multiple Browser Use instances on different ports; round-robin in `browser_control_service.py`

---

## Backups

Supabase handles PostgreSQL backups automatically on paid plans. For the free tier:

```bash
# Manual Postgres backup
pg_dump "$DATABASE_URL" > backup_$(date +%Y%m%d).sql

# Redis backup (snapshot already enabled with appendonly yes)
docker compose exec redis redis-cli bgsave
```

---

## Rollback

```bash
# Roll back to previous image
docker compose pull
git checkout <previous-commit>
docker compose up -d --build

# Roll back database migration (run the down migration manually)
psql "$DATABASE_URL" -f supabase/migrations/rollback/XXXX_rollback.sql
```
