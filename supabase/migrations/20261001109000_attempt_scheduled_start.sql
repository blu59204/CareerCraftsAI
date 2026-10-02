-- Chains pacing between application attempts.
ALTER TABLE public.application_attempts
    ADD COLUMN IF NOT EXISTS scheduled_start_at timestamptz;
