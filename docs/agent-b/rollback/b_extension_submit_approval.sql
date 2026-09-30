-- Drain all apply tasks and restore matching old code before running this.
-- ApplicationAttempt outcome/approved_snapshot_hash evidence is retained.
ALTER TABLE public.extension_tasks
    DROP COLUMN IF EXISTS review_hash,
    DROP COLUMN IF EXISTS review_url,
    DROP COLUMN IF EXISTS review_expires_at,
    DROP COLUMN IF EXISTS approved_at,
    DROP COLUMN IF EXISTS submission_token_hash,
    DROP COLUMN IF EXISTS submission_expires_at,
    DROP COLUMN IF EXISTS submission_reported_at;
