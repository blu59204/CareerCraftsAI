-- Feature-flagged Temporal support (TEMPORAL_ENABLED) — both columns stay
-- NULL for every attempt driven by the default BullMQ/WorkflowTask path.
ALTER TABLE public.application_attempts
    ADD COLUMN workflow_id text UNIQUE,
    ADD COLUMN temporal_run_id text;

CREATE INDEX application_attempts_workflow_id_idx ON public.application_attempts (workflow_id)
    WHERE workflow_id IS NOT NULL;
