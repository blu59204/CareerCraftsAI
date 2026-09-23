# PHASE 2 — ONE FULLY WORKING PATH (the most important phase)

## The slice
Register/Login → Onboarding → Settings: add Anthropic/OpenAI key → Resume page: upload PDF →
click "Optimize for this JD" → watch SSE thinking events → see ATS score + tailored resume → download PDF.
When this works end-to-end in the browser, the platform pattern is proven. Every other agent copies it.

## Sub-tasks (one prompt each, fresh chat each)

### 2.1 Auth round-trip
READ: frontend/src/middleware.ts, lib/supabase/{client,server,middleware}.ts, lib/supabase-token.ts,
      app/auth/callback/route.ts, backend/app/core/supabase_auth.py, api/v1/deps.py, api/v1/users.py
TASK: make GET /api/v1/users/me return the provisioned user for a logged-in browser session. Fix any
      cookie/token mismatch (JWT must be the Supabase access_token, HS256, aud "authenticated").
VERIFY: log in at localhost:3000 → DevTools Network → /users/me → 200 with {id,email,supabase_uid}.

### 2.2 Onboarding guard
READ: components/auth/OnboardingGuard.tsx, app/(app)/onboarding/page.tsx, api/v1/users.py
TASK: onboarding writes profile fields via PATCH /users/me; guard sends to /dashboard after; no loops.
VERIFY: fresh account → /onboarding → complete → /dashboard; refresh → stays on /dashboard.

### 2.3 BYOK key save
READ: app/(app)/settings/models/page.tsx, api/v1/users.py or wherever model settings route is,
      models/model_settings.py, core/security.py, core/model_router.py (get_llm + _build_llm)
TASK: POST model settings encrypts key, stores provider+model+api_key_enc. get_llm() decrypts and builds
      the correct langchain chat model. Add a "Test key" button → POST /users/me/models/test → one tiny
      completion → {"ok":true,"model":...}.
VERIFY: save key → Test → ok:true. DB row api_key_enc is NOT the raw key.

### 2.4 Resume upload → RAG
READ: api/v1/rag.py, services/rag_service.py, services/storage_service.py, models/documents.py,
      app/(app)/resume/page.tsx (upload part)
TASK: upload PDF/DOCX → text extracted → chunks 500/50 → embeddings via user's provider (or fallback
      embedding) → pgvector collection `{user_id}_resume` → documents row. Return {document_id, chunks}.
VERIFY: upload → 200; `select count(*) from langchain_pg_embedding where collection_id=...` > 0.

### 2.5 ResumeAgent end-to-end
READ: agents/resume_agent.py, agents/orchestrator.py, agents/state.py, agents/base_agent.py,
      api/v1/agents.py, api/v1/resume.py, services/{ats_service,pdf_service}.py, core/event_bus.py
TASK: POST /agents/run {task_type:"resume_optimize", context:{document_id, job_description}} →
      agent: emit thinking → retrieve top_k chunks → LLM tailor (system prompt from Phase 3 file; if not yet
      created, a minimal inline one is allowed ONLY here) → ATS score → PDF via pdf_service → store →
      emit complete {result:{resume_markdown, ats_score, keywords_missing, pdf_document_id}} → agent_runs
      updated with status complete + tokens_used.
VERIFY: curl POST /agents/run → run_id; curl -N /agents/{id}/stream → thinking... complete; GET /agents/runs
      shows complete; GET /resume/download/{pdf_document_id} → application/pdf.

### 2.6 Frontend wiring for resume page
READ: app/(app)/resume/page.tsx, lib/sse.ts, store/agentStore.ts, components/agents/AgentStatusStream.tsx,
      components/resume/{AtsScoreRing,KeywordCoverage,SuggestionsList}.tsx, lib/api.ts
TASK: Upload → shows document. JD textarea + "Optimize" → POST /agents/run → initRun(run_id) →
      useAgentStream(run_id) → thinking events appear live in AgentStatusStream → on complete: render
      AtsScoreRing(ats_score), KeywordCoverage(keywords_missing), tailored resume (sanitized), Download PDF
      button → GET /resume/download/{id} as blob. Error event → toast + retry button. No page reload needed.
VERIFY: full flow in browser with DevTools open: 0 console errors, SSE frames visible, PDF downloads.

### 2.7 Slice regression test
TASK: write tests/e2e/test_resume_slice.py (INTEGRATION=1) that: creates test user JWT, saves fake key with a
      mocked get_llm, uploads a fixture PDF, runs resume_optimize, reads SSE until complete, downloads PDF,
      asserts agent_runs row status=complete. Mock only the LLM and embeddings.
VERIFY: cd backend; $env:INTEGRATION="1"; .venv\Scripts\python -m pytest tests\e2e\test_resume_slice.py -v

## PHASE 2 EXIT
[ ] A real human did the slice in a browser and it worked
[ ] test_resume_slice passes
[ ] commit: "feat(slice): resume optimize works end-to-end (auth→byok→upload→agent→sse→pdf)"
