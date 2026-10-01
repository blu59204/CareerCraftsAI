-- The tailored resume PDF that goes with a recruiter email.
ALTER TABLE public.recruiter_outreach
    ADD COLUMN IF NOT EXISTS resume_document_id uuid;
ALTER TABLE public.recruiter_outreach
    ADD COLUMN IF NOT EXISTS sending_at timestamptz;
