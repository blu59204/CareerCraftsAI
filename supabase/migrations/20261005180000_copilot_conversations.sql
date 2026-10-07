BEGIN;
CREATE TABLE IF NOT EXISTS copilot_conversations (
 user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 thread_id varchar(200) NOT NULL,
 title varchar(100) NOT NULL,
 messages jsonb NOT NULL DEFAULT '[]'::jsonb,
 active_run_id varchar(200),
 active_since timestamptz,
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(user_id, thread_id)
);
CREATE INDEX IF NOT EXISTS copilot_conversations_owner_updated ON copilot_conversations(user_id, updated_at DESC);
ALTER TABLE copilot_conversations ENABLE ROW LEVEL SECURITY;
COMMIT;
