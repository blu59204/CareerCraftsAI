-- Migration: 0012_interview_sessions
-- Creates the interview_sessions table for AI mock interview practice
-- Requirement: 2.6

CREATE TABLE interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_application_id UUID REFERENCES job_applications(id),
    role VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    questions JSONB NOT NULL DEFAULT '[]',
    answers JSONB NOT NULL DEFAULT '[]',
    scores JSONB NOT NULL DEFAULT '[]',
    overall_score INTEGER,
    summary JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_is_user ON interview_sessions(user_id, started_at DESC);
