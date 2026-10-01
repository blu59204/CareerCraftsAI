CREATE TABLE IF NOT EXISTS public.job_search_defaults (
 user_id uuid PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
 kind varchar(10) NOT NULL CHECK (kind IN ('resume','persona')),
 basis_id uuid NOT NULL
);
ALTER TABLE public.job_search_defaults ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.job_search_defaults FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.job_search_defaults TO service_role;
CREATE POLICY b_search_default_service ON public.job_search_defaults TO service_role USING (true) WITH CHECK (true);
