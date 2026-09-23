# TESTING — how the small model writes and runs tests

## Layers
unit/        pure logic + agents with mocked get_llm/services/redis/db. Fast. Runs on every commit.
security/    auth (no token/bad aud/expired), CORS rejects *, rate limit 429, HITL cannot be bypassed,
             keys never plaintext in DB/logs, /internal rejects bad secret.
integration/ INTEGRATION=1, real Supabase test project + real Redis, mocked LLM only.
e2e/         the Phase 2 slice + one per agent; SSE read until complete/checkpoint.
frontend/    vitest + @testing-library/react for stores/components; Playwright for the resume slice.

## Fixtures to create once (tests/conftest.py) — give this task first
- `fake_llm(schema)`: returns an object with `.ainvoke()` yielding `AIMessage(content=schema_example_json)`
  and `.usage_metadata={"total_tokens":123}`
- `patch_get_llm(monkeypatch, fake)`: patches core.model_router.get_llm AND services.llm_gateway.get_llm
- `fake_redis`: fakeredis.aioredis or a dict-backed stub with setex/get/publish/subscribe
- `db_session`: SQLite in-memory is NOT enough (pgvector) → for unit tests mock the repository functions;
  for integration use TEST_DATABASE_URL
- `auth_headers(user_id)`: mints HS256 JWT with SUPABASE_JWT_SECRET, aud "authenticated"
- `sse_collect(client, run_id, timeout)`: async generator reading GET /stream, returns list of events

## Test-writing prompt (paste with 01+02 and the file under test)
Write pytest tests for <file>. Use fixtures from conftest (paste). Cover: happy path, each early-return
error, external failure → error shape, HITL → awaiting_approval. One assertion topic per test function.
Name tests test_<function>_<condition>_<expected>. No network. No sleep >0.1s. Output only the test file.

## Resolve the 46 vs 285 drift
cd backend; .venv\Scripts\python -m pytest tests\unit tests\security -q --collect-only | Select -Last 3
Record the real count in README. Whatever it is, is the truth.

## Coverage gates (add to CI)
backend: coverage run -m pytest tests/unit tests/security; coverage report --fail-under=70
frontend: npm run type-check; npm run lint; npm run build
worker: npm run build
security: bandit -r app -q; pip-audit -r requirements.txt; npm audit --audit-level=high

## CI file check
.github/workflows/ci.yml must run the four gates above on PR; cd.yml deploys only on main after ci passes.
