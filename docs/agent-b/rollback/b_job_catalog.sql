DROP TABLE IF EXISTS public.job_match_embeddings,public.job_source_occurrences,public.job_catalog,public.job_source_health;
ALTER TABLE public.job_applications DROP COLUMN IF EXISTS source, DROP COLUMN IF EXISTS posted_at;
