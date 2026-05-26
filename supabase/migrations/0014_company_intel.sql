-- Migration: 0014_company_intel
-- Create company_intel table for storing researched company information per user

CREATE TABLE company_intel (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    overview TEXT,
    culture_summary TEXT,
    news_items JSONB NOT NULL DEFAULT '[]',
    tech_stack JSONB NOT NULL DEFAULT '[]',
    glassdoor_sentiment VARCHAR(10),
    partial_data JSONB,
    researched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, company_name)
);

CREATE INDEX idx_ci_lookup ON company_intel(user_id, company_name);
