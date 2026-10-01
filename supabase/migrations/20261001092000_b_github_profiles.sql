CREATE TABLE public.github_profiles (
 user_id uuid PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
 mode text NOT NULL CHECK(mode IN ('nango','public_url')), login text NOT NULL,
 data jsonb, refreshed_at timestamptz, next_allowed_at timestamptz, deleted_at timestamptz,
 version integer NOT NULL DEFAULT 0
);
ALTER TABLE public.github_profiles ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.github_profiles FROM PUBLIC,anon,authenticated;
GRANT ALL ON public.github_profiles TO service_role;
CREATE POLICY b_github_service ON public.github_profiles TO service_role USING(true) WITH CHECK(true);
