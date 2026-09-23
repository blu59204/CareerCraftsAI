-- Ensure feature tables and pgvector memory tables exist on live databases
-- that missed migrations 0012-0017 or 0023.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    job_application_id UUID REFERENCES public.job_applications(id),
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
CREATE INDEX IF NOT EXISTS idx_is_user ON public.interview_sessions(user_id, started_at DESC);

CREATE TABLE IF NOT EXISTS public.salary_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    job_application_id UUID REFERENCES public.job_applications(id),
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
CREATE INDEX IF NOT EXISTS idx_sr_user ON public.salary_reports(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.company_intel (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS idx_ci_lookup ON public.company_intel(user_id, company_name);

CREATE TABLE IF NOT EXISTS public.resume_personas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    primary_resume_id UUID REFERENCES public.user_documents(id) ON DELETE SET NULL,
    target_keywords JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rp_user ON public.resume_personas(user_id);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'resume_personas'
          AND column_name = 'target_keywords'
          AND udt_name = '_text'
    ) THEN
        -- The column arrives from 0015 as TEXT[] carrying a text[] default.
        -- ALTER TYPE cannot cast that default automatically and fails with
        -- "default for column target_keywords cannot be cast automatically
        -- to type jsonb", so drop it first; the statement after this block
        -- re-establishes it as '[]'::jsonb.
        ALTER TABLE public.resume_personas
            ALTER COLUMN target_keywords DROP DEFAULT;
        ALTER TABLE public.resume_personas
            ALTER COLUMN target_keywords TYPE JSONB
            USING to_jsonb(target_keywords);
    END IF;
END $$;
ALTER TABLE public.resume_personas
    ALTER COLUMN target_keywords SET DEFAULT '[]'::jsonb;

CREATE OR REPLACE FUNCTION public.check_max_personas() RETURNS TRIGGER AS $$
BEGIN
    IF (SELECT COUNT(*) FROM public.resume_personas WHERE user_id = NEW.user_id) >= 10 THEN
        RAISE EXCEPTION 'Maximum 10 resume personas per user';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_max_personas ON public.resume_personas;
CREATE TRIGGER trg_max_personas BEFORE INSERT ON public.resume_personas
    FOR EACH ROW EXECUTE FUNCTION public.check_max_personas();

CREATE TABLE IF NOT EXISTS public.linkedin_outreach_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    company VARCHAR(255) NOT NULL,
    contact_name VARCHAR(255) NOT NULL,
    contact_title VARCHAR(255),
    contact_linkedin_url TEXT,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending_approval'
        CHECK (status IN ('pending_approval', 'approved', 'sent', 'rejected', 'edited')),
    approved_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_loq_user_status ON public.linkedin_outreach_queue(user_id, status);

CREATE TABLE IF NOT EXISTS public.ats_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resume_id UUID REFERENCES public.user_documents(id) ON DELETE SET NULL,
    job_application_id UUID REFERENCES public.job_applications(id),
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
CREATE INDEX IF NOT EXISTS idx_ats_user ON public.ats_scores(user_id, scored_at DESC);

ALTER TABLE public.job_applications
    ADD COLUMN IF NOT EXISTS cover_letter_id UUID REFERENCES public.user_documents(id);

CREATE TABLE IF NOT EXISTS public.cover_letter_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    job_application_id UUID NOT NULL REFERENCES public.job_applications(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES public.user_documents(id) ON DELETE CASCADE,
    tone VARCHAR(10) NOT NULL CHECK (tone IN ('formal', 'casual', 'bold')),
    version_number INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(job_application_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_clv_app
    ON public.cover_letter_versions(job_application_id, created_at DESC);

ALTER TABLE public.user_preferences
    ADD COLUMN IF NOT EXISTS years_experience INTEGER;

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

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'memory_access_log'
          AND constraint_name = 'memory_access_log_user_id_fkey'
    ) THEN
        ALTER TABLE public.memory_access_log
            DROP CONSTRAINT memory_access_log_user_id_fkey;
    END IF;
    ALTER TABLE public.memory_access_log
        ADD CONSTRAINT memory_access_log_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
END $$;

CREATE INDEX IF NOT EXISTS user_memories_hnsw
    ON public.user_memories USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS agent_episodes_hnsw
    ON public.agent_episodes USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS user_memories_uid
    ON public.user_memories (user_id, memory_type, is_active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_learnings_unique
    ON public.agent_learnings (agent_type, learning);

ALTER TABLE public.interview_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salary_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_intel ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resume_personas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.linkedin_outreach_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ats_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cover_letter_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_episodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_learnings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_access_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS interview_sessions_owner ON public.interview_sessions;
DROP POLICY IF EXISTS salary_reports_owner ON public.salary_reports;
DROP POLICY IF EXISTS company_intel_owner ON public.company_intel;
DROP POLICY IF EXISTS resume_personas_owner ON public.resume_personas;
DROP POLICY IF EXISTS linkedin_outreach_queue_owner ON public.linkedin_outreach_queue;
DROP POLICY IF EXISTS ats_scores_owner ON public.ats_scores;
DROP POLICY IF EXISTS cover_letter_versions_owner ON public.cover_letter_versions;
DROP POLICY IF EXISTS user_memories_owner ON public.user_memories;
DROP POLICY IF EXISTS agent_episodes_owner ON public.agent_episodes;
DROP POLICY IF EXISTS memory_access_log_owner ON public.memory_access_log;

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

CREATE POLICY cover_letter_versions_owner ON public.cover_letter_versions
    FOR ALL TO authenticated
    USING (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text))
    WITH CHECK (user_id = (SELECT id FROM public.users WHERE supabase_uid = (SELECT auth.uid())::text));

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
    public.interview_sessions,
    public.salary_reports,
    public.company_intel,
    public.resume_personas,
    public.linkedin_outreach_queue,
    public.ats_scores,
    public.cover_letter_versions,
    public.user_memories,
    public.agent_episodes,
    public.agent_learnings,
    public.memory_access_log
TO authenticated;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;
