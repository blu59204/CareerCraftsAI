-- Roll back together with the old application version, after workflows drain.
BEGIN;
ALTER TABLE public.b_retired_browser_sessions RENAME TO browser_sessions;
ALTER TABLE public.b_retired_browser_account_states RENAME TO browser_account_states;
-- Original RLS policies remain attached through table renames.
GRANT ALL ON public.browser_sessions, public.browser_account_states TO service_role;
COMMIT;
