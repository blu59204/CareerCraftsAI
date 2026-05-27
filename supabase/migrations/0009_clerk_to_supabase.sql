-- Migration 0009: Clerk → Supabase Auth
-- 1. Rename users.clerk_id → users.supabase_uid (kept as TEXT for backfill)
-- 2. Update RLS policies to use auth.uid()::text
-- 3. Trigger on auth.users INSERT → auto-create public.users row

ALTER TABLE public.users RENAME COLUMN clerk_id TO supabase_uid;

DROP POLICY IF EXISTS users_self ON public.users;
DROP POLICY IF EXISTS model_settings_owner ON public.user_model_settings;
DROP POLICY IF EXISTS documents_owner ON public.user_documents;
DROP POLICY IF EXISTS applications_owner ON public.job_applications;
DROP POLICY IF EXISTS leads_owner ON public.leads;
DROP POLICY IF EXISTS agent_runs_owner ON public.agent_runs;

CREATE POLICY users_self ON public.users
    FOR ALL USING (supabase_uid = auth.uid()::text);

CREATE POLICY model_settings_owner ON public.user_model_settings
    FOR ALL USING (
        user_id = (SELECT id FROM public.users WHERE supabase_uid = auth.uid()::text)
    );

CREATE POLICY documents_owner ON public.user_documents
    FOR ALL USING (
        user_id = (SELECT id FROM public.users WHERE supabase_uid = auth.uid()::text)
    );

CREATE POLICY applications_owner ON public.job_applications
    FOR ALL USING (
        user_id = (SELECT id FROM public.users WHERE supabase_uid = auth.uid()::text)
    );

CREATE POLICY leads_owner ON public.leads
    FOR ALL USING (
        user_id = (SELECT id FROM public.users WHERE supabase_uid = auth.uid()::text)
    );

CREATE POLICY agent_runs_owner ON public.agent_runs
    FOR ALL USING (
        user_id = (SELECT id FROM public.users WHERE supabase_uid = auth.uid()::text)
    );

CREATE OR REPLACE FUNCTION public.handle_new_supabase_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.users (email, full_name, avatar_url, supabase_uid)
    VALUES (
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name'),
        NEW.raw_user_meta_data->>'avatar_url',
        NEW.id::text
    )
    ON CONFLICT (email) DO UPDATE
        SET supabase_uid = EXCLUDED.supabase_uid,
            full_name   = COALESCE(public.users.full_name, EXCLUDED.full_name),
            avatar_url  = COALESCE(public.users.avatar_url, EXCLUDED.avatar_url);
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_supabase_user();
