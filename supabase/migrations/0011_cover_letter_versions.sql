-- Migration: 0011_cover_letter_versions
-- Add cover_letter_id to job_applications and create cover_letter_versions table

ALTER TABLE job_applications ADD COLUMN cover_letter_id UUID REFERENCES user_documents(id);

CREATE TABLE cover_letter_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_application_id UUID NOT NULL REFERENCES job_applications(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES user_documents(id) ON DELETE CASCADE,
    tone VARCHAR(10) NOT NULL CHECK (tone IN ('formal', 'casual', 'bold')),
    version_number INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(job_application_id, version_number)
);
CREATE INDEX idx_clv_app ON cover_letter_versions(job_application_id, created_at DESC);
