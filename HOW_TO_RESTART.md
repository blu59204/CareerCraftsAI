# How to Restart CareerCraft AI (Windows PowerShell + Clerk)

## Quick restart (dev stack)
```powershell
cd "D:\CareerCraft AI"
docker compose -f docker-compose.dev.yml restart backend frontend temporal-worker redis
docker compose -f docker-compose.dev.yml ps
curl http://localhost:8000/health
```

## Frontend only (no Docker)
```powershell
cd "D:\CareerCraft AI\frontend"
Remove-Item -Recurse -Force .next -ErrorAction SilentlyContinue
npm run dev
# → http://localhost:3000
```

## Backend only (no Docker)
```powershell
cd "D:\CareerCraft AI\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# docs: http://localhost:8000/docs
```

## If port is busy
```powershell
Get-NetTCPConnection -LocalPort 3000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

## Auth (Clerk)
- Login: http://localhost:3000/login using the providers configured in Clerk.
- Configure Clerk redirect origins for localhost:3000.
- If session verification fails, sign out and sign in again; confirm the Clerk publishable key and backend Clerk configuration match.
- Backend check: logged-in browser → DevTools Network → `GET /api/v1/users/me` → 200

## Logs (read these first on failure)
- `backend-run.log` / `backend-run.err.log` — look for `Authentication required` (Redis) or `Duplicate Operation ID`
- `temporal-worker` Compose logs — look for `Eviction policy` (must be `noeviction`) or `status=403/422` with body
- `frontend-run.err.log` — cosmetic React warnings only (ignore `script tag` warning)

## Redis green checklist
```powershell
docker compose -f docker-compose.dev.yml up -d redis
docker compose -f docker-compose.dev.yml exec redis redis-cli -a $env:REDIS_PASSWORD ping  # → PONG
docker compose -f docker-compose.dev.yml exec redis redis-cli -a $env:REDIS_PASSWORD config get maxmemory-policy  # → noeviction
curl http://localhost:8000/health  # all "ok", else 503 with failing field
```
