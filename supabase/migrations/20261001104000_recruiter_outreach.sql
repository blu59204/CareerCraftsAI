-- Recruiter outreach: one row per email, tracking it from draft to reply.
ALTER TABLE public.user_preferences
    ADD COLUMN IF NOT EXISTS outreach_daily_cap integer NOT NULL DEFAULT 25,
    ADD COLUMN IF NOT EXISTS outreach_auto_send boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS public.recruiter_outreach (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    job_application_id uuid REFERENCES public.job_applications(id) ON DELETE SET NULL,
    parent_id uuid REFERENCES public.recruiter_outreach(id) ON DELETE SET NULL,
    kind varchar(20) NOT NULL DEFAULT 'initial',
    company text NOT NULL,
    role text,
    to_email text NOT NULL,
    email_source varchar(30),
    verdict varchar(10) NOT NULL DEFAULT 'unknown',
    verified_by varchar(30),
    subject text NOT NULL,
    body text NOT NULL,
    resume_version varchar(64),
    state varchar(20) NOT NULL DEFAULT 'draft',
    approved_at timestamptz,
    gmail_message_id text,
    gmail_thread_id text,
    sent_at timestamptz,
    followup_due_at timestamptz,
    replied_at timestamptz,
    bounced_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS recruiter_outreach_user_id ON public.recruiter_outreach (user_id);
CREATE INDEX IF NOT EXISTS recruiter_outreach_state ON public.recruiter_outreach (state);
CREATE UNIQUE INDEX IF NOT EXISTS recruiter_outreach_one_per_kind
    ON public.recruiter_outreach (user_id, job_application_id, kind)
    WHERE job_application_id IS NOT NULL;

ALTER TABLE public.recruiter_outreach ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.recruiter_outreach FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.recruiter_outreach TO service_role;
CREATE POLICY b_recruiter_outreach_service ON public.recruiter_outreach
    TO service_role USING (true) WITH CHECK (true);
