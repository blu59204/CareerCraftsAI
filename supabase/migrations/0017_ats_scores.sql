-- Migration: 0017_ats_scores.sql
-- Description: Create ats_scores table for ATS scoring with composite, keyword, readability, format sub-scores
-- Requirement: 8.6

CREATE TABLE ats_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_id UUID REFERENCES user_documents(id) ON DELETE SET NULL,
    job_application_id UUID REFERENCES job_applications(id),
    composite_score INTEGER NOT NULL,
    keyword_score INTEGER NOT NULL,
    readability_score INTEGER NOT NULL,
    format_score INTEGER NOT NULL,
    missing_keywords JSONB NOT NULL DEFAULT '[]',
    suggestions JSONB NOT NULL DEFAULT '[]',
    flesch_kincaid FLOAT,
    avg_sentence_length FLOAT,
    format_checks JSONB NOT NULL DEFAULT '{}',
    scored_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ats_user ON ats_scores(user_id, scored_at DESC);
