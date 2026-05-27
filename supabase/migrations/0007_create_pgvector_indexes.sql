CREATE EXTENSION IF NOT EXISTS vector;

-- LangChain PGVector manages its own tables (langchain_pg_collection, langchain_pg_embedding)
-- Run after first RAG ingestion in production:
--
-- CREATE INDEX CONCURRENTLY ON langchain_pg_embedding
--   USING hnsw (embedding vector_cosine_ops)
--   WITH (m = 16, ef_construction = 64);
SELECT 1;
