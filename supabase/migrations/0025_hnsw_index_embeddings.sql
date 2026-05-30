-- Create the HNSW index on the LangChain pgvector embedding table.
--
-- Migration 0007 left this commented out ("run after first ingestion"), but
-- CLAUDE.md requires an HNSW index for production scale. LangChain manages
-- langchain_pg_embedding itself, so the table may not exist until the first
-- RAG ingestion — guard creation behind a table-existence check. The app also
-- calls the same CREATE INDEX after first ingestion so clean deploys do not
-- permanently miss the index when this migration runs before LangChain creates
-- the table.
--
-- Note: CREATE INDEX CONCURRENTLY cannot run inside a transaction block (and
-- migration runners typically wrap each file in one), so this uses a plain
-- CREATE INDEX. It briefly locks writes to the embedding table; run during a
-- low-traffic window if the table is already large. To build without locking,
-- run CONCURRENTLY manually outside a migration instead.

CREATE EXTENSION IF NOT EXISTS vector;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'langchain_pg_embedding'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_langchain_embedding_hnsw
            ON public.langchain_pg_embedding
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
    ELSE
        RAISE NOTICE 'langchain_pg_embedding does not exist yet; app ingestion will create the HNSW index after LangChain creates the table.';
    END IF;
END
$$;
