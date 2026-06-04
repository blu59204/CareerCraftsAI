-- Security hardening: enable Row Level Security on public tables that were
-- reachable through PostgREST with RLS disabled (Supabase advisor lint
-- 0013_rls_disabled_in_public, ERROR level), plus tighten two functions.
--
-- These tables are accessed only by the backend, which connects as the
-- `postgres` role (rolbypassrls = true), so enabling RLS with no policy locks
-- out anon/authenticated direct API access while leaving the backend working.
-- Several of these tables are created at runtime by LangChain PGVector or the
-- agent-memory layer, so every statement is guarded with to_regclass().
--
-- Note: `supabase migration new` was unavailable in this environment, so this
-- follows the repository's existing numeric migration naming scheme.

DO $$
DECLARE
    tbl text;
    tables text[] := ARRAY[
        'public.alembic_version',
        'public.agent_memory_preferences',
        'public.agent_memory_episodes',
        'public.agent_memory_learnings',
        'public.agent_memory_procedures',
        'public.agent_learnings',
        'public.langchain_pg_collection',
        'public.langchain_pg_embedding',
        'public."aea7460b-3851-442f-9ae3-53a03409bd84_resume"'
    ];
BEGIN
    FOREACH tbl IN ARRAY tables LOOP
        IF to_regclass(tbl) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', tbl);
        END IF;
    END LOOP;
END $$;

-- The signup trigger fn is SECURITY DEFINER and was callable by anon/authenticated
-- via /rest/v1/rpc/. It only ever runs as an AFTER INSERT trigger on auth.users
-- (executes as its owner), so revoking EXECUTE does not affect provisioning.
DO $$
BEGIN
    IF to_regprocedure('public.handle_new_supabase_user()') IS NOT NULL THEN
        REVOKE EXECUTE ON FUNCTION public.handle_new_supabase_user() FROM anon, authenticated, public;
    END IF;
END $$;

-- Pin a non-mutable search_path on the two trigger functions flagged by the
-- advisor (lint 0011). Their bodies use only builtins / schema-qualified names.
DO $$
BEGIN
    IF to_regprocedure('public.set_updated_at()') IS NOT NULL THEN
        ALTER FUNCTION public.set_updated_at() SET search_path = '';
    END IF;
    IF to_regprocedure('public.check_max_personas()') IS NOT NULL THEN
        ALTER FUNCTION public.check_max_personas() SET search_path = '';
    END IF;
END $$;
