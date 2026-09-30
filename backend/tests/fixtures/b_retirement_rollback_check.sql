DO $$
BEGIN
    ASSERT (SELECT review->>'proof' FROM public.browser_sessions) = 'retained';
    ASSERT (SELECT state_enc FROM public.browser_account_states) = 'encrypted-test-fixture';
    ASSERT has_table_privilege('service_role', 'public.browser_sessions', 'SELECT');
    ASSERT NOT has_table_privilege('authenticated', 'public.browser_account_states', 'SELECT');
    ASSERT (SELECT relrowsecurity FROM pg_class WHERE oid = 'public.browser_sessions'::regclass);
END $$;
