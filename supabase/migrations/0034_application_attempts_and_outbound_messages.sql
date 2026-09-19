-- Backend-only idempotency ledgers: ownership is checked by FastAPI and workers.
CREATE TABLE public.application_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    job_application_id uuid NOT NULL REFERENCES public.job_applications(id) ON DELETE CASCADE,
    run_id uuid REFERENCES public.agent_runs(id) ON DELETE SET NULL,

    state varchar(30) NOT NULL DEFAULT 'preparing'
        CHECK (state IN (
            'preparing', 'awaiting_approval', 'submitting', 'submitted',
            'verified', 'outcome_unknown', 'failed', 'cancelled'
        )),

    submission_token text UNIQUE,
    external_application_id text,
    confirmation_url text,
    confirmation_text text,
    approved_snapshot_hash text,

    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    submitted_at timestamptz,
    verified_at timestamptz,

    UNIQUE (user_id, job_application_id)
);
CREATE INDEX application_attempts_user_idx ON public.application_attempts (user_id);
CREATE INDEX application_attempts_run_idx ON public.application_attempts (run_id);

CREATE TABLE public.outbound_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    run_id uuid REFERENCES public.agent_runs(id) ON DELETE SET NULL,
    channel varchar(20) NOT NULL DEFAULT 'email',
    recipient text NOT NULL,
    subject text,
    body_hash text NOT NULL,

    state varchar(30) NOT NULL DEFAULT 'draft'
        CHECK (state IN ('draft', 'awaiting_approval', 'sending', 'sent', 'outcome_unknown', 'failed')),

    provider_message_id text,
    idempotency_key text NOT NULL UNIQUE,

    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz
);
CREATE INDEX outbound_messages_user_idx ON public.outbound_messages (user_id);
CREATE INDEX outbound_messages_run_idx ON public.outbound_messages (run_id);

ALTER TABLE public.application_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.outbound_messages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.application_attempts, public.outbound_messages FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.application_attempts, public.outbound_messages TO service_role;
CREATE POLICY application_attempts_service ON public.application_attempts TO service_role USING (true) WITH CHECK (true);
CREATE POLICY outbound_messages_service ON public.outbound_messages TO service_role USING (true) WITH CHECK (true);
