-- Add LinkedIn credentials (encrypted) and auto-mode toggle to user preferences
ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_email_enc TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_password_enc TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_mode TEXT DEFAULT 'drafts' CHECK (auto_mode IN ('auto', 'drafts'));
