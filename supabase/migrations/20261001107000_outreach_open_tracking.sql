-- Opt-in open tracking for recruiter emails (off by default).
ALTER TABLE public.user_preferences
    ADD COLUMN IF NOT EXISTS outreach_track_opens boolean NOT NULL DEFAULT false;
ALTER TABLE public.recruiter_outreach
    ADD COLUMN IF NOT EXISTS open_token varchar(40),
    ADD COLUMN IF NOT EXISTS opened_at timestamptz;
CREATE INDEX IF NOT EXISTS recruiter_outreach_open_token
    ON public.recruiter_outreach (open_token);
