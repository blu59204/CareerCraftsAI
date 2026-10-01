DO $$
BEGIN
    ASSERT to_regclass('public.browser_sessions') IS NULL;
    ASSERT to_regclass('public.browser_account_states') IS NULL;
    ASSERT (SELECT count(*) FROM public.b_retired_browser_sessions) = 1;
    ASSERT (SELECT state_enc FROM public.b_retired_browser_account_states) = 'encrypted-test-fixture';
    ASSERT NOT has_table_privilege('service_role', 'public.b_retired_browser_sessions', 'SELECT');
    ASSERT NOT has_table_privilege('authenticated', 'public.b_retired_browser_account_states', 'SELECT');
END $$;
