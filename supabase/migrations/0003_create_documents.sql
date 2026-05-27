CREATE TABLE user_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  doc_type TEXT NOT NULL,
  filename TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  raw_text TEXT,
  embedded_at TIMESTAMPTZ,
  is_primary BOOLEAN DEFAULT false
);

CREATE INDEX idx_documents_user_id ON user_documents(user_id);
CREATE INDEX idx_documents_doc_type ON user_documents(user_id, doc_type);
