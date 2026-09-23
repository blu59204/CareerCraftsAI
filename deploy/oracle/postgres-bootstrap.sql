-- Supabase-compatibility shim for self-hosted Postgres.
--
-- The 33 migrations in supabase/migrations/ were written against Supabase,
-- so they reference things the platform provides rather than the database:
-- the roles `authenticated` and `service_role`, and the functions auth.uid()
-- and auth.jwt(). Creating them here lets every migration apply unchanged,
-- which matters because it keeps one schema history for both environments.
--
-- Runs once, before the migrations, via docker-entrypoint-initdb.d.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Roles referenced by RLS policies (GRANT ... TO authenticated, etc).
-- NOLOGIN: nothing authenticates as these directly. The API connects as the
-- table owner, which bypasses RLS, exactly as it did on Supabase — the
-- backend's own per-request user_id filtering is the enforcing control.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
  END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS auth;
GRANT USAGE ON SCHEMA auth TO anon, authenticated, service_role;

-- Claims are supplied per-connection via SET LOCAL request.jwt.claims.
-- Both spellings exist in the wild (PostgREST used the singular form
-- historically), so accept either and return NULL rather than erroring
-- when nothing is set.
CREATE OR REPLACE FUNCTION auth.jwt()
RETURNS jsonb
LANGUAGE sql STABLE
AS $$
  SELECT COALESCE(
    NULLIF(current_setting('request.jwt.claims', true), ''),
    NULLIF(current_setting('request.jwt.claim', true), '')
  )::jsonb
$$;

-- Mirrors Supabase: casts the subject to UUID. Migration 0028 deliberately
-- uses auth.jwt()->>'sub' instead for Clerk-style text subjects like user_xxx,
-- which would fail this cast — so that path stays text and is unaffected.
CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql STABLE
AS $$
  SELECT NULLIF(auth.jwt() ->> 'sub', '')::uuid
$$;

GRANT EXECUTE ON FUNCTION auth.jwt(), auth.uid() TO anon, authenticated, service_role;
