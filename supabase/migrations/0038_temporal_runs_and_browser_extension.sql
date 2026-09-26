-- Temporal is now the only execution engine, and job applications run in the
-- user's own browser through the CareerCraft extension.

-- 20260909180254_durable_agent_workflows.sql started writing 'queued' and
-- 'expired' run statuses without widening this constraint, so every
-- POST /agents/run failed with a CheckViolation on a freshly migrated
-- database. 'cancelled' is new: a user can now stop a run while it waits.
ALTER TABLE public.agent_runs DROP CONSTRAINT IF EXISTS agent_runs_status_check;
ALTER TABLE public.agent_runs ADD CONSTRAINT agent_runs_status_check
    CHECK (status IN (
        'queued', 'running', 'awaiting_approval', 'completed', 'failed', 'expired', 'cancelled'
    ));

-- One row per paired browser. The raw token is shown once at pairing time;
-- only its SHA-256 is stored, so a database leak cannot drive anyone's browser.
CREATE TABLE public.extension_devices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name varchar(100) NOT NULL DEFAULT 'Browser',
    token_hash varchar(64) NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz,
    revoked_at timestamptz
);
CREATE INDEX extension_devices_user_idx ON public.extension_devices (user_id)
    WHERE revoked_at IS NULL;

-- Work handed to the extension. The Temporal workflow that created a task
-- owns its lifecycle; the extension only claims it and reports progress.
CREATE TABLE public.extension_tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    device_id uuid REFERENCES public.extension_devices(id) ON DELETE SET NULL,
    run_id uuid REFERENCES public.agent_runs(id) ON DELETE CASCADE,
    job_application_id uuid REFERENCES public.job_applications(id) ON DELETE CASCADE,
    workflow_id text NOT NULL,
    kind varchar(30) NOT NULL DEFAULT 'apply' CHECK (kind IN ('apply')),
    status varchar(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'claimed', 'filling', 'needs_input', 'review',
            'login_required', 'submitted', 'failed', 'cancelled', 'expired'
        )),
    payload jsonb NOT NULL DEFAULT '{}',
    result jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    claimed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);
CREATE INDEX extension_tasks_pending_idx ON public.extension_tasks (user_id, created_at)
    WHERE status = 'pending';
CREATE INDEX extension_tasks_run_idx ON public.extension_tasks (run_id);
CREATE UNIQUE INDEX extension_tasks_one_open_per_application
    ON public.extension_tasks (user_id, job_application_id)
    WHERE status IN ('pending', 'claimed', 'filling', 'needs_input', 'review', 'login_required');

ALTER TABLE public.extension_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.extension_tasks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.extension_devices, public.extension_tasks FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.extension_devices, public.extension_tasks TO service_role;
CREATE POLICY extension_devices_service ON public.extension_devices
    TO service_role USING (true) WITH CHECK (true);
CREATE POLICY extension_tasks_service ON public.extension_tasks
    TO service_role USING (true) WITH CHECK (true);
