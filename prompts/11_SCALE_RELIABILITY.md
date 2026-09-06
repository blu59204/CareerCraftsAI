# PHASE 6 — SCALE & RELIABILITY (one prompt per item)

6.1 Timeouts everywhere: every agent node wrapped with asyncio.wait_for using AGENT_TIMEOUTS; every httpx
    client timeout=20; every LLM call timeout via model kwargs; browser step timeout 30s. On timeout → error
    event + agent_runs status "timeout".
6.2 Retries: LLM 2 retries with exponential backoff on 429/5xx (not on 4xx); search providers fall through
    the provider list (Tavily → Brave → SerpAPI → DDG → Searxng); never retry sends.
6.3 Concurrency: enforce AGENT_MAX_CONCURRENT_PER_USER=2 with a redis counter (INCR/EXPIRE) at /agents/run →
    429 with retry_after. BullMQ concurrency per queue set in worker.
6.4 Token budgets: TokenTrackingCallback writes tokens_used; check_budget before each LLM call → 429
    "budget exceeded" event; per-user monthly cap from user_model_settings.token_budget.
6.5 Caching: CachingLLM 1h for company_research/salary/interview_prep only; company_intel 7d; never cache
    email/auto_apply/outreach.
6.6 pgvector: confirm HNSW index migration 0025/0032 applied; RAG retrieve uses cosine; top_k from settings.
6.7 Browser: one Playwright context per user, max BROWSER_USE_MAX_CONCURRENT_SESSIONS, auto-close after
    run, memory guard psutil; screenshots to browser_debug volume only in debug mode.
6.8 Observability: request_id in every log line and every SSE event payload; structured JSON logs
    (LOG_LEVEL from settings); agent_runs stores duration_ms, tokens_used, strategy_used, error; /health
    adds queue depth (BullMQ waiting/active/failed counts) and last-successful-cron timestamps.
6.9 BullBoard: add worker/src/board.ts serving @bull-board/api + express on :3010, bound to 127.0.0.1 only,
    behind Nginx basic-auth at /admin/queues. Never public.
6.10 Dead-letter + idempotency: failed BullMQ jobs → `failed` queue with attempts=3, backoff exponential 30s;
     jobId = f"{user_id}:{task_type}:{hash(context)}" so duplicate clicks don't double-run; followup jobs
     keyed by application_id so cancel-on-reply is `queue.remove(jobId)`.
6.11 Graceful shutdown: backend lifespan closes redis pool + engine; worker handles SIGTERM → wait for active
     jobs (30s) → exit; compose stop_grace_period 45s.
6.12 Load test: locustfile.py scenarios: /users/me (60%), /agents/runs (25%), POST resume_optimize with
     mocked LLM (15%). Target: p95 <500ms for reads, 0 5xx at 20 users. Record numbers in docs/DEPLOYMENT.md.
6.13 Backups: Supabase PITR on; redis appendonly volume; documents bucket lifecycle (delete PDFs >90d
     unless attached to an application).

VERIFY per item: the specific test the model writes for it + a manual run. Commit each separately:
"perf(<area>): <item>".
