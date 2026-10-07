-- Optional selections should not prevent a member deleting their own file.
-- Application history remains; its deleted artifact selections become NULL.
ALTER TABLE public.job_applications
    DROP CONSTRAINT IF EXISTS job_applications_resume_id_fkey,
    DROP CONSTRAINT IF EXISTS job_applications_cover_letter_id_fkey,
    ADD CONSTRAINT job_applications_resume_id_fkey
        FOREIGN KEY (resume_id) REFERENCES public.user_documents(id) ON DELETE SET NULL,
    ADD CONSTRAINT job_applications_cover_letter_id_fkey
        FOREIGN KEY (cover_letter_id) REFERENCES public.user_documents(id) ON DELETE SET NULL;

ALTER TABLE public.candidate_profiles
    DROP CONSTRAINT IF EXISTS candidate_profiles_default_resume_id_fkey,
    ADD CONSTRAINT candidate_profiles_default_resume_id_fkey
        FOREIGN KEY (default_resume_id) REFERENCES public.user_documents(id) ON DELETE SET NULL;
