-- Opt-in: the agent tailors a resume and queues applications for saved jobs
-- above the match-score threshold. Nothing is submitted without the member's
-- review in their own browser.
ALTER TABLE public.user_preferences
    ADD COLUMN IF NOT EXISTS auto_apply_enabled boolean NOT NULL DEFAULT false;
