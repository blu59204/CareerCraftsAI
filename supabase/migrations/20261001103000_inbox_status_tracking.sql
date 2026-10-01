-- Application status tracking from the member's own inbox.
-- Opt-in: reading a mailbox on a schedule never starts unasked.
ALTER TABLE public.user_preferences
    ADD COLUMN IF NOT EXISTS inbox_tracking_enabled boolean NOT NULL DEFAULT false;

-- One row per Gmail message already acted on, so a message is never applied
-- twice and a status never moves because of the same email on a later scan.
CREATE TABLE IF NOT EXISTS public.application_status_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    job_application_id uuid REFERENCES public.job_applications(id) ON DELETE SET NULL,
    gmail_message_id text NOT NULL,
    category text NOT NULL,
    company text,
    subject text,
    previous_status text,
    new_status text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, gmail_message_id)
);
CREATE INDEX IF NOT EXISTS application_status_events_application
    ON public.application_status_events (job_application_id);

ALTER TABLE public.application_status_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.application_status_events FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.application_status_events TO service_role;
CREATE POLICY b_status_events_service ON public.application_status_events
    TO service_role USING (true) WITH CHECK (true);
