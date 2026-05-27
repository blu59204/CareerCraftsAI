-- Fix RLS policies: migrate from clerk_id to supabase_uid
-- Finding AUTHZ-001: RLS policies referenced stale clerk_id column

-- Drop old policies
DROP POLICY IF EXISTS users_self ON users;
DROP POLICY IF EXISTS model_settings_owner ON user_model_settings;
DROP POLICY IF EXISTS documents_owner ON user_documents;
DROP POLICY IF EXISTS applications_owner ON job_applications;
DROP POLICY IF EXISTS leads_owner ON leads;
DROP POLICY IF EXISTS agent_runs_owner ON agent_runs;

-- Recreate with supabase_uid
CREATE POLICY users_self ON users
    FOR ALL USING (supabase_uid = auth.jwt() ->> 'sub');

CREATE POLICY model_settings_owner ON user_model_settings
    FOR ALL USING (
        user_id = (SELECT id FROM users WHERE supabase_uid = auth.jwt() ->> 'sub')
    );

CREATE POLICY documents_owner ON user_documents
    FOR ALL USING (
        user_id = (SELECT id FROM users WHERE supabase_uid = auth.jwt() ->> 'sub')
    );

CREATE POLICY applications_owner ON job_applications
    FOR ALL USING (
        user_id = (SELECT id FROM users WHERE supabase_uid = auth.jwt() ->> 'sub')
    );

CREATE POLICY leads_owner ON leads
    FOR ALL USING (
        user_id = (SELECT id FROM users WHERE supabase_uid = auth.jwt() ->> 'sub')
    );

CREATE POLICY agent_runs_owner ON agent_runs
    FOR ALL USING (
        user_id = (SELECT id FROM users WHERE supabase_uid = auth.jwt() ->> 'sub')
    );
