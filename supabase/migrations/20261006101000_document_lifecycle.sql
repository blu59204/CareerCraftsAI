-- No FK: cleanup must survive removal of the document and account.
CREATE TABLE IF NOT EXISTS document_cleanup_queue (
    document_id uuid PRIMARY KEY,
    user_id uuid NOT NULL,
    storage_path text NOT NULL,
    filename text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    next_attempt_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE document_cleanup_queue ADD COLUMN IF NOT EXISTS
    next_attempt_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE document_cleanup_queue ENABLE ROW LEVEL SECURITY;
-- Backend maintenance owns this table; no browser/client grants.
REVOKE ALL ON document_cleanup_queue FROM PUBLIC;

-- Recover legacy ownership only where a filename identifies exactly one live
-- owner/type document. Ambiguous or deleted sources must never be retrieved.
DO $$
BEGIN
    IF to_regclass('public.langchain_pg_embedding') IS NOT NULL THEN
        UPDATE langchain_pg_embedding e
        SET cmetadata = e.cmetadata || jsonb_build_object('document_id', owned.id)
        FROM (
            SELECT user_id::text AS owner, doc_type, filename, min(id::text) AS id
            FROM user_documents GROUP BY user_id, doc_type, filename HAVING count(*) = 1
        ) owned
        WHERE e.cmetadata->>'document_id' IS NULL
          AND e.cmetadata->>'user_id' = owned.owner
          AND e.cmetadata->>'doc_type' = owned.doc_type
          AND e.cmetadata->>'filename' = owned.filename;

        DELETE FROM langchain_pg_embedding e
        WHERE e.cmetadata->>'document_id' IS NULL
           OR NOT EXISTS (
               SELECT 1 FROM user_documents d
               WHERE d.id::text = e.cmetadata->>'document_id'
                 AND d.user_id::text = e.cmetadata->>'user_id'
           );
    END IF;
END $$;

DO $$
DECLARE dimension integer;
BEGIN
    IF to_regclass('public.langchain_pg_embedding') IS NOT NULL THEN
        FOREACH dimension IN ARRAY ARRAY[768, 1024, 1536] LOOP
            EXECUTE format(
                'CREATE INDEX IF NOT EXISTS idx_langchain_embedding_hnsw_%s '
                'ON langchain_pg_embedding USING hnsw '
                '((embedding::vector(%s)) vector_cosine_ops) '
                'WITH (m = 16, ef_construction = 64) WHERE vector_dims(embedding) = %s',
                dimension, dimension, dimension
            );
        END LOOP;
    END IF;
END $$;
