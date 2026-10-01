-- Drain apply tasks first. Rows in the new states are mapped to their nearest
-- old equivalent so the original CHECK can be restored without deleting data.
BEGIN;
UPDATE public.extension_tasks SET status = 'failed', completed_at = coalesce(completed_at, now())
    WHERE status IN ('submitting', 'outcome_unknown');
ALTER TABLE public.extension_tasks DROP CONSTRAINT IF EXISTS extension_tasks_status_check;
ALTER TABLE public.extension_tasks ADD CONSTRAINT extension_tasks_status_check
    CHECK (status IN (
        'pending', 'claimed', 'filling', 'needs_input', 'review',
        'login_required', 'submitted', 'failed', 'cancelled', 'expired'
    ));
DROP INDEX IF EXISTS public.extension_tasks_one_open_per_application;
CREATE UNIQUE INDEX extension_tasks_one_open_per_application
    ON public.extension_tasks (user_id, job_application_id)
    WHERE status IN ('pending', 'claimed', 'filling', 'needs_input', 'review', 'login_required');
COMMIT;
