CREATE TABLE public.extension_tasks (id uuid PRIMARY KEY, payload jsonb NOT NULL);
ALTER TABLE public.extension_tasks ENABLE ROW LEVEL SECURITY;
INSERT INTO public.extension_tasks VALUES ('00000000-0000-0000-0000-000000000001', '{"preserved":true}');
