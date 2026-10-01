-- Opt-in: a daily email summarising applications and recruiter emails.
ALTER TABLE public.user_preferences
    ADD COLUMN IF NOT EXISTS notify_daily_summary boolean NOT NULL DEFAULT false;
