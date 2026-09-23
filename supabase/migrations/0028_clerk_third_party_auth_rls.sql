-- Clerk Third-Party Auth session tokens use a text `sub` claim such as
-- user_xxx. Do not use auth.uid() for these policies because auth.uid() casts
-- the subject to UUID. Match ownership through auth.jwt()->>'sub' instead.
--
-- Note: `supabase migration new` was unavailable in this local environment, so
-- this follows the repository's existing numeric migration naming scheme.

DROP POLICY IF EXISTS users_self ON public.users;
DROP POLICY IF EXISTS model_settings_owner ON public.user_model_settings;
DROP POLICY IF EXISTS documents_owner ON public.user_documents;
DROP POLICY IF EXISTS applications_owner ON public.job_applications;
DROP POLICY IF EXISTS leads_owner ON public.leads;
DROP POLICY IF EXISTS agent_runs_owner ON public.agent_runs;
DROP POLICY IF EXISTS preferences_owner ON public.user_preferences;

DROP POLICY IF EXISTS cover_letter_versions_owner ON public.cover_letter_versions;
DROP POLICY IF EXISTS interview_sessions_owner ON public.interview_sessions;
DROP POLICY IF EXISTS salary_reports_owner ON public.salary_reports;
DROP POLICY IF EXISTS company_intel_owner ON public.company_intel;
DROP POLICY IF EXISTS resume_personas_owner ON public.resume_personas;
DROP POLICY IF EXISTS linkedin_outreach_queue_owner ON public.linkedin_outreach_queue;
DROP POLICY IF EXISTS ats_scores_owner ON public.ats_scores;
DROP POLICY IF EXISTS agent_memory_episodes_owner ON public.agent_memory_episodes;
DROP POLICY IF EXISTS agent_memory_learnings_owner ON public.agent_memory_learnings;
DROP POLICY IF EXISTS agent_memory_preferences_owner ON public.agent_memory_preferences;
DROP POLICY IF EXISTS agent_memory_procedures_owner ON public.agent_memory_procedures;
DROP POLICY IF EXISTS user_memories_owner ON public.user_memories;
DROP POLICY IF EXISTS agent_episodes_owner ON public.agent_episodes;
DROP POLICY IF EXISTS memory_access_log_owner ON public.memory_access_log;

CREATE POLICY users_self ON public.users
    FOR ALL TO authenticated
    USING (supabase_uid = (SELECT auth.jwt() ->> 'sub'))
    WITH CHECK (supabase_uid = (SELECT auth.jwt() ->> 'sub'));

CREATE POLICY model_settings_owner ON public.user_model_settings
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY documents_owner ON public.user_documents
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY applications_owner ON public.job_applications
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY leads_owner ON public.leads
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY agent_runs_owner ON public.agent_runs
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY preferences_owner ON public.user_preferences
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY cover_letter_versions_owner ON public.cover_letter_versions
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY interview_sessions_owner ON public.interview_sessions
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY salary_reports_owner ON public.salary_reports
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY company_intel_owner ON public.company_intel
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY resume_personas_owner ON public.resume_personas
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY linkedin_outreach_queue_owner ON public.linkedin_outreach_queue
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY ats_scores_owner ON public.ats_scores
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY agent_memory_episodes_owner ON public.agent_memory_episodes
    FOR ALL TO authenticated
    USING (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY agent_memory_learnings_owner ON public.agent_memory_learnings
    FOR ALL TO authenticated
    USING (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY agent_memory_preferences_owner ON public.agent_memory_preferences
    FOR ALL TO authenticated
    USING (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY agent_memory_procedures_owner ON public.agent_memory_procedures
    FOR ALL TO authenticated
    USING (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY user_memories_owner ON public.user_memories
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY agent_episodes_owner ON public.agent_episodes
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

CREATE POLICY memory_access_log_owner ON public.memory_access_log
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.jwt() ->> 'sub')));

GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_preferences TO authenticated;
