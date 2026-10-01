-- Drain application workflows for the retired executor before deployment.
-- Archive encrypted state without purging data or modifying applied history.
BEGIN;
DO $$
BEGIN
    IF to_regclass('public.browser_sessions') IS NOT NULL THEN
        ALTER TABLE public.browser_sessions RENAME TO b_retired_browser_sessions;
    END IF;
    IF to_regclass('public.browser_account_states') IS NOT NULL THEN
        ALTER TABLE public.browser_account_states RENAME TO b_retired_browser_account_states;
    END IF;
END $$;
REVOKE ALL ON public.b_retired_browser_sessions,
    public.b_retired_browser_account_states FROM PUBLIC, anon, authenticated, service_role;
COMMIT;
