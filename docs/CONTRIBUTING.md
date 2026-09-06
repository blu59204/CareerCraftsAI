# Contributing

Thanks for contributing to CareerCraft AI. This document covers the PR process, code standards, and how to add new features.

---

## Getting Started

1. Fork the repo and clone your fork
2. Follow the [Development Guide](docs/DEVELOPMENT.md) to set up locally
3. Create a branch: `git checkout -b feat/my-feature`
4. Make your changes
5. Write or update tests
6. Open a PR against `main`

---

## Branch Naming

| Prefix | Use for |
|---|---|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `chore/` | Dependency updates, tooling, config |
| `docs/` | Documentation only |
| `test/` | Test additions or fixes |
| `refactor/` | Code restructuring without behavior change |

---

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add salary benchmarking to company research output
fix: resume ATS score not updating after re-upload
chore: pin langchain-core to 1.4.0 for CVE-2025-68664
docs: add agent timeout reference to AGENTS.md
test: add integration test for Gmail send approval flow
```

---

## Pull Request Requirements

Before opening a PR, verify:

**Backend:**
```bash
cd backend
pytest tests/unit tests/security -v        # all 403 collected tests pass
bandit -r app/ -f txt                       # no HIGH severity findings
ruff check . && black --check .            # no lint errors
```

**Frontend:**
```bash
cd frontend
npm run type-check                          # no TypeScript errors
npm run lint                                # no ESLint errors
npm test                                    # jest tests pass
```

PRs that fail CI will not be merged.

---

## PR Description Template

```markdown
## What this does
One or two sentences describing the change.

## Why
What problem does this solve? Link to an issue if relevant.

## Testing
- What did you test manually?
- Are there new automated tests?

## Checklist
- [ ] Tests pass
- [ ] No bandit HIGH findings
- [ ] No TypeScript errors
- [ ] AGENTS.md / API.md updated if applicable
- [ ] No secrets committed
```

---

## Code Standards

### Python

- Type hints on all function signatures
- `async`/`await` for all DB and HTTP calls
- Pydantic models for all request/response schemas — no raw dicts in API handlers
- No hardcoded model names — always use the model router
- No raw SQL with user input — use SQLAlchemy ORM or parameterized queries

### TypeScript

- No `any` type without a comment explaining why
- `'use client'` only when the component needs browser APIs or interactivity
- TanStack Query for data fetching — no `useEffect` + `fetch`
- Zustand for global state — no prop drilling past 2 levels

### General

- No secrets or API keys in code or comments
- No `console.log` left in frontend code (use `logger` in backend, remove debug logs from frontend before PR)
- One responsibility per file — avoid 500-line modules

---

## Adding a New Agent

See [AGENTS.md](../AGENTS.md) for the full agent reference. When adding a new agent:

1. Create `backend/app/agents/my_agent.py`
2. Add routing in `orchestrator.py`
3. Create `backend/app/api/v1/my_agent.py` with the API endpoint
4. Register the router in `backend/app/main.py`
5. Add Pydantic schemas in `models/schemas.py`
6. Write tests in `tests/unit/test_my_agent.py` (mock the LLM — never call real APIs in unit tests)
7. Add the agent to `AGENTS.md`

---

## Adding a New Database Table

1. Create `supabase/migrations/XXXX_create_my_table.sql`
2. Include the table definition, indexes, and RLS policy
3. Add the SQLAlchemy model in `backend/app/models/db.py`
4. Add Pydantic schemas in `backend/app/models/schemas.py`
5. Apply locally: `supabase db push --db-url "$DATABASE_URL"`
6. Document in `docs/DATABASE.md`

Every new user-data table must have RLS:
```sql
ALTER TABLE public.my_table ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users see own rows" ON public.my_table
  FOR ALL
  USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = auth.uid()));
```

---

## What We Won't Merge

- Code that hardcodes model names (use the model router)
- Code that sends emails or submits applications without the HITL gate
- Storing API keys in plaintext (must encrypt via `security.py`)
- Removing or weakening RLS policies
- Skipping the SUPABASE_JWT_SECRET verification
- Adding dependencies with known HIGH/CRITICAL CVEs
- Test code that calls real external APIs (mock them)

---

## Questions

Open a GitHub Discussion or reach out via the issue tracker. For security issues, see [docs/SECURITY.md](docs/SECURITY.md#reporting-a-security-issue).
