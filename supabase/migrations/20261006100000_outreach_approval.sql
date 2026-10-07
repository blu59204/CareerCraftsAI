-- Approval binds each message and attachment to an explicitly reviewed payload.
ALTER TABLE public.recruiter_outreach
    ADD COLUMN IF NOT EXISTS approved_payload_hash varchar(64);
-- Legacy automatic approvals do not establish consent for the current payload.
UPDATE public.recruiter_outreach
SET state = 'draft', approved_at = NULL, approved_payload_hash = NULL
WHERE state = 'approved';
