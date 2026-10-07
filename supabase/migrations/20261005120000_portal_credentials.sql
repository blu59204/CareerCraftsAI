BEGIN;
CREATE TABLE IF NOT EXISTS portal_credentials (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  origin varchar(255) NOT NULL,
  label varchar(100) NOT NULL,
  username_enc text NOT NULL,
  password_enc text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT portal_credentials_user_origin UNIQUE(user_id, origin)
);
CREATE INDEX IF NOT EXISTS portal_credentials_user_id_idx ON portal_credentials(user_id);
ALTER TABLE portal_credentials ENABLE ROW LEVEL SECURITY;
-- Backend performs member-scoped access; no browser database grants.
COMMIT;
