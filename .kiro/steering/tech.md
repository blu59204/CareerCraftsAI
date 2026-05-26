# Tech Stack

## Frontend

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript 5
- **Styling:** Tailwind CSS 3 + shadcn/ui (Radix UI primitives)
- **State:** Zustand 4 (client state) + TanStack Query 5 (server state/caching)
- **Auth:** `@supabase/ssr` — cookie-based sessions; middleware refreshes tokens automatically
- **HTTP:** axios 1.6 + `@microsoft/fetch-event-source` for SSE streams
- **Animations:** Motion (Framer Motion successor)
- **Notifications:** Sonner

## Backend

- **Language:** Python 3.12
- **Framework:** FastAPI 0.111+ with async/await throughout
- **ORM:** SQLAlchemy 2.0 async + asyncpg driver
- **Validation:** Pydantic v2
- **Auth:** Supabase JWT verified locally via `SUPABASE_JWT_SECRET` (HS256, audience=`authenticated`)
- **Rate limiting:** slowapi (60 req/min per user)
- **Security:** AES-256-GCM encryption (cryptography lib) for API keys; PBKDF2 key derivation
- **PDF:** ReportLab 4
- **Doc parsing:** PyMuPDF (PDF) + python-docx (DOCX)
- **Email delivery:** Resend

## Agent Layer

- **Orchestration:** LangGraph 0.2+ (supervisor pattern)
- **LLM abstraction:** LangChain 0.3+ / langchain-core 0.3+
- **Provider integrations:** langchain-anthropic, langchain-openai, langchain-google-genai, langchain-ollama
- **Vector store:** langchain-postgres 0.0.17 (PGVector class) — collections namespaced `{user_id}_{doc_type}`
- **RAG chunking:** RecursiveCharacterTextSplitter, chunk_size=500, overlap=50
- **Browser automation:** PinchTab 0.7.6 (separate Docker service, port 9867)

## Worker

- **Runtime:** Node.js
- **Language:** TypeScript 5
- **Queue:** BullMQ 5 backed by Redis 7 (ioredis)
- **Max concurrency per user:** 2

## Infrastructure

- **Database:** Supabase (PostgreSQL 16 + pgvector 0.7+)
- **Cache/Queue broker:** Redis 7
- **Storage:** Supabase Storage (S3-compatible) for resume PDFs and uploads
- **Auth provider:** Supabase Auth (Google OAuth, LinkedIn OIDC, GitHub, email/password, magic link)
- **Proxy:** Nginx (TLS 1.2/1.3, security headers; `/internal/*` blocked from public)
- **Containers:** Docker Compose (dev + prod configs)
- **CI/CD:** GitHub Actions (`.github/workflows/ci.yml` + `cd.yml`)

## Linting & Formatting

- **Python:** ruff (line-length=100, target py312) + black (line-length=100)
- **TypeScript:** ESLint via `eslint-config-next`
- **Security scan:** bandit on `app/`
- **Dependency audit:** pip-audit + npm audit in CI

---

## Common Commands

### Full Stack (from repo root)

```bash
make dev              # start full stack with hot reload (docker-compose.dev.yml)
make build            # build all Docker images
make test             # run backend unit tests
make lint             # ruff + black check (backend) + eslint (frontend)
make format           # ruff --fix + black + eslint --fix
make clean            # stop containers, remove volumes
```

### Backend

```bash
cd backend
source .venv/bin/activate          # Linux/macOS
# .venv_win\Scripts\activate       # Windows

pip install -r requirements.txt -c constraints.txt   # always use constraints.txt

uvicorn app.main:app --reload --port 8000

pytest tests/unit -v               # 40 unit tests
pytest tests/security -v           # 6 security tests
pytest tests/unit tests/security -v  # all 46 tests
pytest -k "test_name" -v           # single test by name
pytest tests/integration -v        # opt-in: requires INTEGRATION=1 env var

bandit -r app/ -f txt              # SAST scan
ruff check . && black --check .    # lint check
ruff check --fix . && black .      # auto-fix
```

### Frontend

```bash
cd frontend
npm install
npm run dev           # dev server :3000
npm run build         # production build
npm run lint          # eslint
npm run type-check    # tsc --noEmit
```

### Worker

```bash
cd worker
npm install
npm run build         # compile TypeScript
npm run dev           # ts-node (dev mode)
npm start             # run compiled dist/
```

### Database

```bash
supabase db push --db-url "$DATABASE_URL"   # apply migrations
supabase db reset                            # WARNING: drops all data
```

### Load Testing

```bash
# Requires running server + LOAD_TEST_TOKEN env var
locust --host=http://localhost:8000 --users=20 --spawn-rate=4 --run-time=30s --headless
```
