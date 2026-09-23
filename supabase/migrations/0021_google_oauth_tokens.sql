-- Store Google OAuth tokens for Gmail send/read. Values are AES-GCM encrypted by backend.
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS google_access_token_enc TEXT,
  ADD COLUMN IF NOT EXISTS google_refresh_token_enc TEXT,
  ADD COLUMN IF NOT EXISTS google_token_expires_at TIMESTAMPTZ;
