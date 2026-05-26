-- Migration: 0015_resume_personas
-- Requirements: 9.1 (Resume Personas table), 9.2 (target_keywords text array), 9.7 (max 10 personas per user)

CREATE TABLE resume_personas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    primary_resume_id UUID REFERENCES user_documents(id) ON DELETE SET NULL,
    target_keywords TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_rp_user ON resume_personas(user_id);

-- Trigger to enforce max 10 personas per user (Requirement 9.7)
CREATE OR REPLACE FUNCTION check_max_personas() RETURNS TRIGGER AS $$
BEGIN
    IF (SELECT COUNT(*) FROM resume_personas WHERE user_id = NEW.user_id) >= 10 THEN
        RAISE EXCEPTION 'Maximum 10 resume personas per user';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_max_personas BEFORE INSERT ON resume_personas
    FOR EACH ROW EXECUTE FUNCTION check_max_personas();
