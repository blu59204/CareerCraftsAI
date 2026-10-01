-- Per-user RAG lookups filter langchain_pg_embedding by collection_id before
-- the vector search. Moved here from a stray backend/supabase/migrations
-- file that no deploy ever applied; its HNSW index is already in 0025.
-- LangChain creates the table on first ingestion, so this is a no-op until then.
DO $$
BEGIN
    IF to_regclass('public.langchain_pg_embedding') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_langchain_embedding_collection_id
            ON public.langchain_pg_embedding (collection_id);
    END IF;
END
$$;
