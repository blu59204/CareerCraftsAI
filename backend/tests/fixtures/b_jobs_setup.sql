CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;
CREATE TABLE public.users(id uuid PRIMARY KEY);
CREATE TABLE public.job_applications(id uuid PRIMARY KEY,notes text);
INSERT INTO public.users VALUES('00000000-0000-0000-0000-000000000001');
INSERT INTO public.job_applications VALUES('00000000-0000-0000-0000-000000000001','preserved');
