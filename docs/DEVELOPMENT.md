# Development Guide

Everything you need to run CareerCraft AI locally, write and run tests, and follow the project's conventions.

---

## Local Setup

### Prerequisites

- Python 3.12
- Node.js 20+
- Docker + Docker Compose
- Supabase CLI (`brew install supabase/tap/supabase` or see [docs](https://supabase.com/docs/guides/cli))
- A Supabase project (free tier works)

### Clone

```bash
git clone https://github.com/blu59204/CareerCraftsAI.git
cd CareerCraftsAI
cp .env.example .env
```

Fill in `.env` with at minimum:
- `APP_SECRET_KEY` (any 32-char string in dev)
- `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `REDIS_URL=redis://localhost:6379`

---

## Running the Stack

### Option A: Full Docker Compose (recommended for integration work)

```bash
make dev
# or: docker compose -f docker-compose.dev.yml up
```

Services start with hot reload:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Redis: localhost:6379

### Option B: Individual services (faster for focused work)

**Backend only:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

pip install -r requirements.txt -c constraints.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend only:**
```bash
cd frontend
npm install
npm run dev
```

**Worker only:**
```bash
cd worker
npm install
npm run dev
```

**Redis (local):**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

---

## Database Setup

```bash
# Apply all migrations to your Supabase project
supabase db push --db-url "$DATABASE_URL"

# After first document upload, create HNSW index (migration 0007)
# This runs automatically with db push
```

---

## Testing

### Backend (pytest)

```bash
cd backend
source .venv/bin/activate

# All tests (46 total)
pytest tests/unit tests/security -v

# Unit tests only (40, fast, no external services)
pytest tests/unit -v

# Security tests only (6)
pytest tests/security -v

# Single test by name
pytest -k "test_ats_scoring" -v

# With coverage
pytest tests/unit tests/security --cov=app --cov-report=term-missing

# Integration tests (requires real DB + Redis; set INTEGRATION=1)
INTEGRATION=1 pytest tests/integration -v
```

### Frontend (Jest)

```bash
cd frontend
npm test                                     # all tests
npm test -- --testPathPattern=Dashboard     # single file
npm run type-check                           # tsc --noEmit
```

### Security scan

```bash
cd backend
bandit -r app/ -f txt           # SAST (blocks on HIGH severity in CI)
pip-audit                        # dependency CVE check
```

```bash
cd frontend
npm audit                        # dependency CVE check
```

### Load testing

Requires a running server and `LOAD_TEST_TOKEN` env var:

```bash
LOAD_TEST_TOKEN=<jwt> locust \
  --host=http://localhost:8000 \
  --users=20 --spawn-rate=4 --run-time=30s --headless
```

---

## Makefile Commands

```bash
make dev          # start full dev stack (hot reload)
make build        # build all Docker images
make test         # pytest + jest
make lint         # ruff + eslint (check only)
make format       # ruff --fix + black + eslint --fix
make clean        # stop containers, remove volumes
make logs         # tail all service logs
```

---

## Project Conventions

### Python (backend)

- **Formatter:** `black` (line length 88)
- **Linter:** `ruff` (extends flake8 + isort)
- **Type hints:** required on all function signatures
- **Async:** all DB calls must use `async`/`await` with `AsyncSession`
- **Pydantic:** all request/response schemas in `app/models/schemas.py`
- **Config:** all settings via `app/core/config.py` (pydantic-settings) — no hardcoded values

```bash
ruff check . && black --check .    # lint check
ruff check . --fix && black .      # auto-fix
```

### TypeScript (frontend)

- **Formatter:** Prettier (defaults)
- **Linter:** ESLint (`next/core-web-vitals` config)
- **Types:** strict TypeScript — no `any` without comment
- **Components:** functional components with explicit return type
- **State:** Zustand for global state, TanStack Query for server state — no prop drilling
- **Imports:** absolute imports via `@/` alias

```bash
npm run lint          # eslint check
npm run type-check    # tsc --noEmit
```

### Git

- Branch from `main`
- Branch naming: `feat/short-description`, `fix/short-description`, `chore/...`
- Commit messages: conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`)
- PR requires: passing tests, no `bandit` HIGH findings, no TypeScript errors

---

## Environment Variables

Full reference in [docs/CONFIGURATION.md](CONFIGURATION.md). Key dev values:

```bash
APP_ENV=development                # enables /docs, debug logging
APP_SECRET_KEY=dev-secret-32chars  # any 32-char string locally
LOG_LEVEL=DEBUG                    # verbose backend logging
```

---

## Adding a New Agent

1. Create `backend/app/agents/my_agent.py` — subclass `BaseAgent` or write a plain LangGraph graph
2. Add routing logic in `orchestrator.py` (`task_keyword → my_agent`)
3. Create API endpoint in `backend/app/api/v1/my_agent.py`
4. Register router in `backend/app/main.py`
5. Add Pydantic schemas in `models/schemas.py`
6. Write unit tests in `tests/unit/test_my_agent.py`
7. Document in `AGENTS.md`

---

## Adding a New API Endpoint

1. Add route function in the appropriate `api/v1/*.py` file
2. Use `Depends(get_current_user)` and `Depends(get_db)` for auth + DB
3. Use `Depends(limiter.limit("60/minute"))` for rate limiting
4. Add request/response Pydantic models in `models/schemas.py`
5. Test with `pytest tests/unit -k "test_new_endpoint"`

---

## Adding a Database Migration

```bash
# Create migration file
touch supabase/migrations/0020_my_change.sql

# Write SQL
cat > supabase/migrations/0020_my_change.sql << 'EOF'
-- Migration: add column
ALTER TABLE public.applications ADD COLUMN source text;

-- Enable RLS policy if adding new table
ALTER TABLE public.new_table ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users see own rows" ON public.new_table
  FOR ALL USING ((SELECT id FROM users WHERE supabase_uid = auth.uid()) = user_id);
EOF

# Apply
supabase db push --db-url "$DATABASE_URL"
```

---

## Frontend Component Patterns

### Server component (App Router)
```tsx
// app/(app)/dashboard/page.tsx
export default async function DashboardPage() {
  const supabase = createServerClient()
  const { data: user } = await supabase.auth.getUser()
  // fetch initial data...
  return <Dashboard initialData={...} />
}
```

### Client component with TanStack Query
```tsx
// components/applications/ApplicationsList.tsx
'use client'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export function ApplicationsList() {
  const { data, isLoading } = useQuery({
    queryKey: ['applications'],
    queryFn: () => api.get('/jobs/applications').then(r => r.data)
  })
  // ...
}
```

### Zustand store slice
```tsx
// store/agentStore.ts
interface AgentStore {
  activeRunId: string | null
  events: AgentEvent[]
  startRun: (runId: string) => void
  addEvent: (event: AgentEvent) => void
}

export const useAgentStore = create<AgentStore>((set) => ({
  activeRunId: null,
  events: [],
  startRun: (runId) => set({ activeRunId: runId, events: [] }),
  addEvent: (event) => set(s => ({ events: [...s.events, event] })),
}))
```

---

## Debugging

### Backend

```bash
# Enable SQL query logging
LOG_LEVEL=DEBUG uvicorn app.main:app --reload --port 8000

# Test a specific agent locally
cd backend
python -c "
import asyncio
from app.agents.resume_agent import ResumeAgent

async def main():
    agent = ResumeAgent(user_id='test-user')
    result = await agent.run({'job_description': 'Python engineer...'})
    print(result)

asyncio.run(main())
"
```

### Redis

```bash
# Monitor all Redis commands
docker compose exec redis redis-cli monitor

# View BullMQ queue
docker compose exec redis redis-cli lrange bull:job-search:wait 0 -1

# Check active agent state
docker compose exec redis redis-cli get "agent:{run_id}:state"
```

### Frontend SSE

Open browser DevTools → Network tab → filter by `stream` → inspect EventStream for your agent run.

---

## Common Issues

**`ModuleNotFoundError: langchain_postgres`**
→ Install with `pip install -r requirements.txt -c constraints.txt`. The constraints file pins `langchain-postgres==0.0.17`.

**`JWT decode error: audience invalid`**
→ Make sure `SUPABASE_JWT_SECRET` in `.env` matches the JWT secret in Supabase dashboard → Settings → API.

**`pgvector extension not found`**
→ pgvector must be enabled in your Supabase project. Go to Database → Extensions and enable `vector`.

**Frontend 401 errors in dev**
→ Check that `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are set in `.env` (frontend reads these from Next.js env). Restart the frontend dev server after changing `.env`.

**BullMQ jobs not processing**
→ Ensure Redis is running (`docker compose ps redis`) and `REDIS_URL` matches the running instance. Check worker logs: `docker compose logs -f worker`.
