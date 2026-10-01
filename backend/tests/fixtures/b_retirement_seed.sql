INSERT INTO public.browser_sessions (run_id, user_id, expires_at, review)
VALUES ('00000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000001', now(), '{"proof":"retained"}');
INSERT INTO public.browser_account_states (user_id, state_enc)
VALUES ('00000000-0000-0000-0000-000000000001', 'encrypted-test-fixture');
