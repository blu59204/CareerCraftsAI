CREATE TABLE salary_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_application_id UUID REFERENCES job_applications(id),
    role VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    location VARCHAR(255) NOT NULL,
    p25 INTEGER NOT NULL,
    p50 INTEGER NOT NULL,
    p75 INTEGER NOT NULL,
    offer_amount INTEGER,
    classification VARCHAR(20),
    negotiation_script JSONB,
    data_sources JSONB NOT NULL DEFAULT '[]',
    data_unavailable BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sr_user ON salary_reports(user_id, created_at DESC);
