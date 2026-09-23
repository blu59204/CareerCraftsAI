-- Align live schema with ORM fields used by dashboard/auth routes.

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS linkedin_email_enc TEXT,
    ADD COLUMN IF NOT EXISTS linkedin_password_enc TEXT,
    ADD COLUMN IF NOT EXISTS auto_mode TEXT DEFAULT 'drafts';

ALTER TABLE public.job_applications
    ADD COLUMN IF NOT EXISTS cover_letter_id UUID REFERENCES public.user_documents(id);
