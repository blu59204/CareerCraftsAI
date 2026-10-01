-- Existing task RLS and user/device ownership also cover these columns.
-- Drain old extension/workflow versions before upgrading. Never reset attempts.
ALTER TABLE public.extension_tasks
    ADD COLUMN IF NOT EXISTS review_hash varchar(64),
    ADD COLUMN IF NOT EXISTS review_url text,
    ADD COLUMN IF NOT EXISTS review_expires_at timestamptz,
    ADD COLUMN IF NOT EXISTS approved_at timestamptz,
    ADD COLUMN IF NOT EXISTS submission_token_hash varchar(64),
    ADD COLUMN IF NOT EXISTS submission_expires_at timestamptz,
    ADD COLUMN IF NOT EXISTS submission_reported_at timestamptz;
