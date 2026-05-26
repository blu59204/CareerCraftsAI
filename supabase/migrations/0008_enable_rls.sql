-- Enable Row Level Security on all user-scoped tables.
-- All policies restrict rows to the authenticated user's own data.

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_model_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;

-- users: each row is the user itself
CREATE POLICY users_self ON users
    FOR ALL USING (clerk_id = auth.jwt() ->> 'sub');

-- user_model_settings: keyed by user_id FK
CREATE POLICY model_settings_owner ON user_model_settings
    FOR ALL USING (
        user_id = (SELECT id FROM users WHERE clerk_id = auth.jwt() ->> 'sub')
    );

-- user_documents
CREATE POLICY documents_owner ON user_documents
    FOR ALL USING (
        user_id = (SELECT id FROM users WHERE clerk_id = auth.jwt() ->> 'sub')
    );

-- job_applications
CREATE POLICY applications_owner ON job_applications
    FOR ALL USING (
        user_id = (SELECT id FROM users WHERE clerk_id = auth.jwt() ->> 'sub')
    );

-- leads
CREATE POLICY leads_owner ON leads
    FOR ALL USING (
        user_id = (SELECT id FROM users WHERE clerk_id = auth.jwt() ->> 'sub')
    );

-- agent_runs
CREATE POLICY agent_runs_owner ON agent_runs
    FOR ALL USING (
        user_id = (SELECT id FROM users WHERE clerk_id = auth.jwt() ->> 'sub')
    );
