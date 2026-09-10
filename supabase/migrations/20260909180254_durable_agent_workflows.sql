-- Backend-only tables: ownership is checked by FastAPI and workers.
CREATE TABLE public.workflow_tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES public.agent_runs(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    kind varchar(30) NOT NULL CHECK (kind IN ('execute', 'continue')),
    payload jsonb NOT NULL DEFAULT '{}',
    status varchar(30) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'dispatched', 'running', 'completed', 'failed')),
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_until timestamptz,
    error text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX workflow_tasks_dispatch_idx ON public.workflow_tasks (available_at)
    WHERE status IN ('pending', 'dispatched');
CREATE INDEX workflow_tasks_lease_idx ON public.workflow_tasks (lease_until)
    WHERE status = 'running';
CREATE INDEX workflow_tasks_run_idx ON public.workflow_tasks (run_id);
CREATE INDEX workflow_tasks_user_idx ON public.workflow_tasks (user_id);
CREATE UNIQUE INDEX workflow_tasks_one_active_stage ON public.workflow_tasks (run_id)
    WHERE status IN ('pending', 'dispatched', 'running');

CREATE TABLE public.browser_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL UNIQUE REFERENCES public.agent_runs(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    sandbox_id text,
    status varchar(30) NOT NULL DEFAULT 'provisioning',
    expires_at timestamptz NOT NULL,
    review jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX browser_sessions_user_idx ON public.browser_sessions (user_id);
CREATE INDEX browser_sessions_expiry_idx ON public.browser_sessions (expires_at);
CREATE INDEX agent_runs_active_user_idx ON public.agent_runs (user_id, status)
    WHERE status IN ('queued', 'running', 'awaiting_approval');

ALTER TABLE public.workflow_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.browser_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.workflow_tasks, public.browser_sessions FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.workflow_tasks, public.browser_sessions TO service_role;
CREATE POLICY workflow_tasks_service ON public.workflow_tasks TO service_role USING (true) WITH CHECK (true);
CREATE POLICY browser_sessions_service ON public.browser_sessions TO service_role USING (true) WITH CHECK (true);

CREATE TABLE public.browser_account_states (
    user_id uuid PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    state_enc text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.browser_account_states ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.browser_account_states FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.browser_account_states TO service_role;
CREATE POLICY browser_account_states_service ON public.browser_account_states
    TO service_role USING (true) WITH CHECK (true);
