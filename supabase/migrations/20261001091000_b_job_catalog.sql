CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE public.job_source_health (
 source_id text PRIMARY KEY, checked_at timestamptz, next_allowed_at timestamptz,
 status text NOT NULL DEFAULT 'unknown', failures integer NOT NULL DEFAULT 0,
 warning text, cached_jobs jsonb NOT NULL DEFAULT '[]'
);
CREATE TABLE public.job_catalog (
 job_id text PRIMARY KEY, url text NOT NULL UNIQUE, title text NOT NULL, company text NOT NULL,
 posted_at timestamptz, first_seen_at timestamptz NOT NULL DEFAULT now(),
 last_seen_at timestamptz NOT NULL DEFAULT now(), data jsonb NOT NULL
);
CREATE INDEX b_jobs_posted ON public.job_catalog(posted_at DESC);
CREATE INDEX b_jobs_seen ON public.job_catalog(last_seen_at DESC);
CREATE INDEX b_jobs_title ON public.job_catalog USING gin(lower(title) gin_trgm_ops);
CREATE TABLE public.job_source_occurrences (
 job_id text REFERENCES public.job_catalog(job_id) ON DELETE CASCADE,
 source_id text REFERENCES public.job_source_health(source_id) ON DELETE CASCADE,
 last_seen_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(job_id,source_id)
);
CREATE INDEX b_occurrence_source ON public.job_source_occurrences(source_id,job_id);
CREATE TABLE public.job_match_embeddings (
 user_id uuid REFERENCES public.users(id) ON DELETE CASCADE,
 job_id text REFERENCES public.job_catalog(job_id) ON DELETE CASCADE,
 provider text NOT NULL, dimensions integer NOT NULL CHECK(dimensions IN (768,1024,1536)),
 content_hash text NOT NULL, embedding vector NOT NULL,
 PRIMARY KEY(user_id,job_id,provider,dimensions)
);
CREATE INDEX b_job_embeddings_768 ON public.job_match_embeddings USING hnsw ((embedding::vector(768)) vector_cosine_ops) WHERE dimensions=768;
CREATE INDEX b_job_embeddings_1024 ON public.job_match_embeddings USING hnsw ((embedding::vector(1024)) vector_cosine_ops) WHERE dimensions=1024;
CREATE INDEX b_job_embeddings_1536 ON public.job_match_embeddings USING hnsw ((embedding::vector(1536)) vector_cosine_ops) WHERE dimensions=1536;
ALTER TABLE public.job_applications ADD COLUMN source text, ADD COLUMN posted_at timestamptz;
ALTER TABLE public.job_source_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_source_occurrences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_match_embeddings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.job_source_health,public.job_catalog,public.job_source_occurrences,public.job_match_embeddings FROM PUBLIC,anon,authenticated;
GRANT ALL ON public.job_source_health,public.job_catalog,public.job_source_occurrences,public.job_match_embeddings TO service_role;
CREATE POLICY b_source_service ON public.job_source_health TO service_role USING(true) WITH CHECK(true);
CREATE POLICY b_catalog_service ON public.job_catalog TO service_role USING(true) WITH CHECK(true);
CREATE POLICY b_occurrence_service ON public.job_source_occurrences TO service_role USING(true) WITH CHECK(true);
CREATE POLICY b_embedding_service ON public.job_match_embeddings TO service_role USING(true) WITH CHECK(true);
