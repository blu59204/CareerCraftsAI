-- Add WITH CHECK clauses to the core-6 RLS policies.
--
-- Migrations 0008/0009/0018 created these policies with USING only and no
-- WITH CHECK. Without WITH CHECK, INSERT and UPDATE are not validated against
-- the policy, so an authenticated user could write rows carrying another
-- user's user_id (the row is rejected on read but the write succeeds, and a
-- crafted UPDATE could move rows between users). Recreate each policy with
-- both USING and WITH CHECK, matching the pattern established in 0023.

-- Drop existing core-6 policies
DROP POLICY IF EXISTS users_self ON public.users;
DROP POLICY IF EXISTS model_settings_owner ON public.user_model_settings;
DROP POLICY IF EXISTS documents_owner ON public.user_documents;
DROP POLICY IF EXISTS applications_owner ON public.job_applications;
DROP POLICY IF EXISTS leads_owner ON public.leads;
DROP POLICY IF EXISTS agent_runs_owner ON public.agent_runs;

-- users: keyed directly on supabase_uid
CREATE POLICY users_self ON public.users
    FOR ALL TO authenticated
    USING (supabase_uid = (SELECT auth.uid())::text)
    WITH CHECK (supabase_uid = (SELECT auth.uid())::text);

-- All other core tables: keyed on user_id resolved from the users table
CREATE POLICY model_settings_owner ON public.user_model_settings
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY documents_owner ON public.user_documents
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY applications_owner ON public.job_applications
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY leads_owner ON public.leads
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY agent_runs_owner ON public.agent_runs
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));
