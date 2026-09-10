-- Migration 0032: RLS policy gaps + HNSW parameter hardening
--
-- Audit performed 2026-06-13 covering migrations 0008 through 0031.
--
-- ============================================================
-- FINDINGS
-- ============================================================
--
-- 1. VERIFIED OK — core-6 tables (users, user_model_settings, user_documents,
--    job_applications, leads, agent_runs):
--    Final policies set by 0028. All have USING + WITH CHECK scoped to
--    auth.jwt()->>'sub'. No cross-user leakage possible.
--
-- 2. VERIFIED OK — secondary user-scoped tables (cover_letter_versions,
--    interview_sessions, salary_reports, company_intel, resume_personas,
--    linkedin_outreach_queue, ats_scores, user_preferences):
--    Final policies set by 0028. All have USING + WITH CHECK. No leakage.
--
-- 3. VERIFIED OK — memory tables (agent_memory_episodes, agent_memory_learnings,
--    agent_memory_preferences, agent_memory_procedures, user_memories,
--    agent_episodes, memory_access_log):
--    Final policies set by 0028. All have USING + WITH CHECK. No leakage.
--
-- 4. VERIFIED OK — langchain_pg_embedding HNSW index (0025):
--    Uses vector_cosine_ops, m=16, ef_construction=64. Correct.
--
-- 5. VERIFIED OK — user_memories_hnsw / agent_episodes_hnsw (0023/0026):
--    Created without explicit m/ef_construction so pgvector defaults apply
--    (m=16, ef_construction=64). Those are the same values we want, but
--    they are implicit — we recreate them with explicit params for clarity
--    and future-proofing if pgvector changes defaults.
--
-- 6. BUG — agent_learnings:
--    RLS enabled in 0023, 0026, and 0030. NO POLICY was ever created.
--    Table has no user_id column (it is shared cross-agent learning data,
--    not per-user). With RLS on and no policy, Postgres blocks ALL access
--    including the authenticated role. The backend connects as the postgres
--    role (rolbypassrls = true) so backend writes still work, but any
--    future service connecting as `authenticated` will see an empty table
--    with no error — a silent failure. Fix: add an explicit deny policy
--    for authenticated and a service_role bypass policy.
--
-- 7. BUG — langchain_pg_collection / langchain_pg_embedding / alembic_version:
--    RLS enabled in 0030 with NO POLICIES. Backend (postgres role) is fine.
--    But the LangChain PGVector library, if ever configured with the
--    service_role key instead of a direct postgres connection, would be
--    silently blocked. Add explicit service_role bypass policies.
--
-- ============================================================
-- FIX 1: agent_learnings — explicit deny-all-authenticated + service_role allow
-- ============================================================
--
-- agent_learnings has no user_id. It is a global shared table written only
-- by the backend (postgres/service_role). Authenticated users must not read
-- or write it directly via PostgREST.

DROP POLICY IF EXISTS agent_learnings_deny_authenticated ON public.agent_learnings;
DROP POLICY IF EXISTS agent_learnings_service_role ON public.agent_learnings;

-- Deny all authenticated direct access (explicit, documents intent)
CREATE POLICY agent_learnings_deny_authenticated ON public.agent_learnings
    FOR ALL TO authenticated
    USING (false)
    WITH CHECK (false);

-- Allow service_role full access (needed if LangChain or agents use service key)
CREATE POLICY agent_learnings_service_role ON public.agent_learnings
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================
-- FIX 2: langchain_pg_collection / langchain_pg_embedding / alembic_version
--        Explicit service_role bypass + deny authenticated.
-- ============================================================

DO $$
BEGIN
    -- langchain_pg_collection
    IF to_regclass('public.langchain_pg_collection') IS NOT NULL THEN
        EXECUTE $q$
            DROP POLICY IF EXISTS langchain_pg_collection_deny_authenticated ON public.langchain_pg_collection;
            DROP POLICY IF EXISTS langchain_pg_collection_service_role ON public.langchain_pg_collection;
            CREATE POLICY langchain_pg_collection_deny_authenticated ON public.langchain_pg_collection
                FOR ALL TO authenticated USING (false) WITH CHECK (false);
            CREATE POLICY langchain_pg_collection_service_role ON public.langchain_pg_collection
                FOR ALL TO service_role USING (true) WITH CHECK (true);
        $q$;
    END IF;

    -- langchain_pg_embedding
    IF to_regclass('public.langchain_pg_embedding') IS NOT NULL THEN
        EXECUTE $q$
            DROP POLICY IF EXISTS langchain_pg_embedding_deny_authenticated ON public.langchain_pg_embedding;
            DROP POLICY IF EXISTS langchain_pg_embedding_service_role ON public.langchain_pg_embedding;
            CREATE POLICY langchain_pg_embedding_deny_authenticated ON public.langchain_pg_embedding
                FOR ALL TO authenticated USING (false) WITH CHECK (false);
            CREATE POLICY langchain_pg_embedding_service_role ON public.langchain_pg_embedding
                FOR ALL TO service_role USING (true) WITH CHECK (true);
        $q$;
    END IF;

    -- alembic_version
    IF to_regclass('public.alembic_version') IS NOT NULL THEN
        EXECUTE $q$
            DROP POLICY IF EXISTS alembic_version_deny_authenticated ON public.alembic_version;
            DROP POLICY IF EXISTS alembic_version_service_role ON public.alembic_version;
            CREATE POLICY alembic_version_deny_authenticated ON public.alembic_version
                FOR ALL TO authenticated USING (false) WITH CHECK (false);
            CREATE POLICY alembic_version_service_role ON public.alembic_version
                FOR ALL TO service_role USING (true) WITH CHECK (true);
        $q$;
    END IF;
END $$;

-- ============================================================
-- FIX 3: Harden HNSW index params on user_memories and agent_episodes.
--        Indexes created in 0023/0026 used implicit pgvector defaults
--        (m=16, ef_construction=64). Recreate with explicit params.
-- ============================================================

DO $$
BEGIN
    -- user_memories
    IF to_regclass('public.user_memories') IS NOT NULL THEN
        DROP INDEX IF EXISTS public.user_memories_hnsw;
        EXECUTE $q$
            CREATE INDEX IF NOT EXISTS user_memories_hnsw
                ON public.user_memories
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
        $q$;
    END IF;

    -- agent_episodes
    IF to_regclass('public.agent_episodes') IS NOT NULL THEN
        DROP INDEX IF EXISTS public.agent_episodes_hnsw;
        EXECUTE $q$
            CREATE INDEX IF NOT EXISTS agent_episodes_hnsw
                ON public.agent_episodes
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
        $q$;
    END IF;
END $$;

-- ============================================================
-- SQL-LEVEL REGRESSION TESTS (comments — run manually in psql)
-- ============================================================
--
-- Setup: run as postgres/superuser then SET ROLE.
--
-- SET LOCAL ROLE authenticated;
-- SET LOCAL "request.jwt.claims" = '{"sub":"user-A-uid","role":"authenticated"}';
--
-- Test 1: User A cannot read User B's job_applications
--   SELECT COUNT(*) FROM public.job_applications;
--   Expected: 0 rows (only User A's own rows returned by RLS filter)
--
-- Test 2: User A cannot INSERT a job_application for User B
--   INSERT INTO public.job_applications (user_id, job_title, company, status)
--   VALUES (
--       (SELECT id FROM public.users WHERE supabase_uid = 'user-B-uid'),
--       'Engineer', 'ACME', 'applied'
--   );
--   Expected: ERROR: new row violates row-level security policy
--
-- Test 3: User A cannot UPDATE another user's agent_run
--   UPDATE public.agent_runs SET status = 'hacked'
--   WHERE user_id = (SELECT id FROM public.users WHERE supabase_uid = 'user-B-uid');
--   Expected: UPDATE 0  (RLS silently skips non-owned rows)
--
-- Test 4: Authenticated user cannot read agent_learnings
--   SELECT COUNT(*) FROM public.agent_learnings;
--   Expected: 0 (deny policy returns empty set, not an error)
--
-- Test 5: Service_role can read agent_learnings
--   RESET ROLE; SET LOCAL ROLE service_role;
--   SELECT COUNT(*) FROM public.agent_learnings;
--   Expected: actual row count
--
-- Test 6: Authenticated user cannot read langchain_pg_embedding
--   SET LOCAL ROLE authenticated;
--   SELECT COUNT(*) FROM public.langchain_pg_embedding;
--   Expected: 0 rows (deny policy)
--
-- Test 7: users_self WITH CHECK prevents uid hijack
--   SET LOCAL "request.jwt.claims" = '{"sub":"user-A-uid","role":"authenticated"}';
--   UPDATE public.users SET supabase_uid = 'user-B-uid'
--   WHERE supabase_uid = 'user-A-uid';
--   Expected: ERROR: new row violates row-level security policy
--
-- Test 8: User A cannot read User B's user_documents
--   SELECT COUNT(*) FROM public.user_documents;
--   Expected: only User A's documents returned
--
-- Test 9: INSERT into user_documents for another user blocked
--   INSERT INTO public.user_documents (user_id, file_name, file_type, storage_path)
--   VALUES (
--       (SELECT id FROM public.users WHERE supabase_uid = 'user-B-uid'),
--       'resume.pdf', 'pdf', 'fake/path'
--   );
--   Expected: ERROR: new row violates row-level security policy
