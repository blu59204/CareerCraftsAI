-- Disposable PostgreSQL only: dependencies for the original browser-state schema.
CREATE ROLE anon;
CREATE ROLE authenticated;
CREATE ROLE service_role;
CREATE TABLE public.users (id uuid PRIMARY KEY);
CREATE TABLE public.agent_runs (
    id uuid PRIMARY KEY, user_id uuid REFERENCES public.users(id), status text
);
INSERT INTO public.users VALUES ('00000000-0000-0000-0000-000000000001');
INSERT INTO public.agent_runs VALUES (
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001', 'completed'
);
