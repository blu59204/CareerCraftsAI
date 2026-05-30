-- Secure tables added after the initial RLS migration and move memory schema
-- creation into migration history instead of relying only on app-side lazy DDL.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.agent_memory_episodes (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    agent_type TEXT NOT NULL,
    task_type TEXT NOT NULL,
    strategy TEXT NOT NULL DEFAULT 'standard',
    success BOOLEAN NOT NULL DEFAULT FALSE,
    context_summary TEXT,
    output_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_episodes_user_agent
    ON public.agent_memory_episodes (user_id, agent_type, created_at DESC);

CREATE TABLE IF NOT EXISTS public.agent_memory_learnings (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    agent_type TEXT NOT NULL,
    learning TEXT NOT NULL,
    success_rate FLOAT NOT NULL DEFAULT 0.0,
    sample_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, agent_type, learning)
);
CREATE INDEX IF NOT EXISTS idx_learnings_user_agent
    ON public.agent_memory_learnings (user_id, agent_type, success_rate DESC);

CREATE TABLE IF NOT EXISTS public.agent_memory_preferences (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    preference_key TEXT NOT NULL,
    preference_value TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, preference_key)
);
CREATE INDEX IF NOT EXISTS idx_agent_memory_prefs_user
    ON public.agent_memory_preferences (user_id);

CREATE TABLE IF NOT EXISTS public.agent_memory_procedures (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    agent_type TEXT NOT NULL,
    trigger_desc TEXT NOT NULL,
    workflow_json TEXT NOT NULL,
    success_count INT NOT NULL DEFAULT 1,
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, agent_type, trigger_desc)
);
CREATE INDEX IF NOT EXISTS idx_procedures_user_agent
    ON public.agent_memory_procedures (user_id, agent_type, success_count DESC);

CREATE TABLE IF NOT EXISTS public.user_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    memory_type TEXT NOT NULL CHECK (memory_type IN ('preference','fact','outcome','blacklist','skill','style')),
    content TEXT NOT NULL,
    embedding vector(1536),
    source_agent TEXT,
    confidence FLOAT DEFAULT 1.0,
    times_used INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.agent_episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    agent_type TEXT NOT NULL,
    summary TEXT,
    input JSONB,
    output JSONB,
    outcome TEXT CHECK (outcome IN ('success','failure','pending','skipped')),
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.agent_learnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type TEXT NOT NULL,
    learning TEXT NOT NULL,
    evidence_count INTEGER DEFAULT 1,
    success_rate FLOAT DEFAULT 1.0,
    last_applied TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.memory_access_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id),
    query TEXT,
    results JSONB,
    agent_type TEXT,
    accessed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS user_memories_hnsw
    ON public.user_memories USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS agent_episodes_hnsw
    ON public.agent_episodes USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS user_memories_uid
    ON public.user_memories (user_id, memory_type, is_active);

ALTER TABLE public.cover_letter_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interview_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salary_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_intel ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resume_personas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.linkedin_outreach_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ats_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_memory_episodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_memory_learnings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_memory_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_memory_procedures ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_episodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_learnings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_access_log ENABLE ROW LEVEL SECURITY;

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

CREATE POLICY cover_letter_versions_owner ON public.cover_letter_versions
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY interview_sessions_owner ON public.interview_sessions
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY salary_reports_owner ON public.salary_reports
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY company_intel_owner ON public.company_intel
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY resume_personas_owner ON public.resume_personas
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY linkedin_outreach_queue_owner ON public.linkedin_outreach_queue
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY ats_scores_owner ON public.ats_scores
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY agent_memory_episodes_owner ON public.agent_memory_episodes
    FOR ALL TO authenticated
    USING (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY agent_memory_learnings_owner ON public.agent_memory_learnings
    FOR ALL TO authenticated
    USING (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY agent_memory_preferences_owner ON public.agent_memory_preferences
    FOR ALL TO authenticated
    USING (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY agent_memory_procedures_owner ON public.agent_memory_procedures
    FOR ALL TO authenticated
    USING (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id::text FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY user_memories_owner ON public.user_memories
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY agent_episodes_owner ON public.agent_episodes
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

CREATE POLICY memory_access_log_owner ON public.memory_access_log
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

GRANT SELECT, INSERT, UPDATE, DELETE ON
    public.cover_letter_versions,
    public.interview_sessions,
    public.salary_reports,
    public.company_intel,
    public.resume_personas,
    public.linkedin_outreach_queue,
    public.ats_scores,
    public.agent_memory_episodes,
    public.agent_memory_learnings,
    public.agent_memory_preferences,
    public.agent_memory_procedures,
    public.user_memories,
    public.agent_episodes,
    public.memory_access_log
TO authenticated;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;
