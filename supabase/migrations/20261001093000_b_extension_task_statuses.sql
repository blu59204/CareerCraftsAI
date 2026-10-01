-- Allow the extension submit lifecycle states written by the approval flow:
-- 'submitting' (approved, token issued) and 'outcome_unknown' (unverifiable).
-- 'submitting' is still open work, so it joins the one-open-per-application index.
BEGIN;
ALTER TABLE public.extension_tasks DROP CONSTRAINT IF EXISTS extension_tasks_status_check;
ALTER TABLE public.extension_tasks ADD CONSTRAINT extension_tasks_status_check
    CHECK (status IN (
        'pending', 'claimed', 'filling', 'needs_input', 'review', 'login_required',
        'submitting', 'submitted', 'outcome_unknown', 'failed', 'cancelled', 'expired'
    ));
DROP INDEX IF EXISTS public.extension_tasks_one_open_per_application;
CREATE UNIQUE INDEX extension_tasks_one_open_per_application
    ON public.extension_tasks (user_id, job_application_id)
    WHERE status IN (
        'pending', 'claimed', 'filling', 'needs_input', 'review', 'login_required', 'submitting'
    );
COMMIT;
