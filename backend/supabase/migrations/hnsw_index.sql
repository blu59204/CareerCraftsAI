-- Migration: HNSW index on langchain_pg_embedding for production-scale vector search
-- Run: psql $DATABASE_URL -f supabase/migrations/hnsw_index.sql
-- Safe to run multiple times (IF NOT EXISTS guards).
--
-- Without HNSW, pgvector defaults to exact KNN (full table scan).
-- At 10k+ vectors per user, exact KNN exceeds acceptable latency for RAG retrieval.
-- HNSW reduces retrieve() latency from O(n) → O(log n) at the cost of ~2× index build time.
--
-- Parameters chosen for a multi-tenant workload:
--   m = 16              (graph connectivity; 16 is the pgvector default, good for general use)
--   ef_construction = 64 (build-time search width; higher = better recall, slower build)
--   cosine ops          (matches the OpenAI/Google/nomic-embed-text embedding space)
--
-- Monitoring query (check index is used, not seqscan):
--   EXPLAIN (ANALYZE, BUFFERS)
--   SELECT * FROM langchain_pg_embedding
--   ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
--   LIMIT 5;

-- Ensure pgvector extension is present
CREATE EXTENSION IF NOT EXISTS vector;

-- HNSW index for cosine similarity (used by LangChain PGVector retrieve())
CREATE INDEX IF NOT EXISTS idx_langchain_embedding_hnsw
    ON public.langchain_pg_embedding
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Collection-scoped index: speeds up per-user collection queries
-- (LangChain PGVector filters by collection_id before vector similarity)
CREATE INDEX IF NOT EXISTS idx_langchain_embedding_collection_id
    ON public.langchain_pg_embedding (collection_id);

-- RLS policies for langchain_pg_embedding (application-layer enforcement):
-- The backend uses SUPABASE_SERVICE_KEY which bypasses Postgres RLS.
-- Isolation is enforced at the application layer via collection_name namespacing:
--   collection_name = "{user_id}_{doc_type}_{provider}_{dim}d"
-- Each user's vectors are in a separate named collection; no cross-collection
-- reads are possible through the LangChain PGVector API.
-- To add DB-level enforcement later, switch backend connections to per-user
-- JWTs (anon key + RLS) instead of the service key.
