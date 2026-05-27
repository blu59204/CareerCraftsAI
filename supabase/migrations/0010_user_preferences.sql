-- Migration 0010: User preferences table + profile columns
-- 1. Add profile columns to users
-- 2. Add ATS columns to user_documents
-- 3. Create user_preferences table with RLS

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS phone TEXT,
    ADD COLUMN IF NOT EXISTS linkedin_url TEXT,
    ADD COLUMN IF NOT EXISTS headline TEXT,
    ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.user_documents
    ADD COLUMN IF NOT EXISTS ats_score INTEGER,
    ADD COLUMN IF NOT EXISTS ats_data JSONB;

CREATE TABLE IF NOT EXISTS public.user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    experience_level TEXT,
    job_type TEXT,
    work_mode TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    target_roles JSONB DEFAULT '[]'::jsonb,
    preferred_locations JSONB DEFAULT '[]'::jsonb,
    current_title TEXT,
    bio TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY preferences_owner ON public.user_preferences
    FOR ALL USING (
        user_id = (SELECT id FROM public.users WHERE supabase_uid = auth.uid()::text)
    );

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS user_preferences_updated_at ON public.user_preferences;
CREATE TRIGGER user_preferences_updated_at
    BEFORE UPDATE ON public.user_preferences
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
