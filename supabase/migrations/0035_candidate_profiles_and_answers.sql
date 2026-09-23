-- Backend-only structured application data: ownership is checked by FastAPI.
CREATE TABLE public.candidate_profiles (
    user_id uuid PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,

    first_name text,
    last_name text,
    email text,
    phone text,

    city text,
    state text,
    country text,
    postal_code text,

    current_company text,
    current_title text,
    years_experience numeric,
    notice_period_days integer,

    linkedin_url text,
    github_url text,
    portfolio_url text,

    current_salary numeric,
    expected_salary numeric,
    currency varchar(10),

    work_authorization text,
    requires_sponsorship boolean,
    willing_to_relocate boolean,
    remote_preference text,

    default_resume_id uuid REFERENCES public.user_documents(id),
    version integer NOT NULL DEFAULT 1,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.candidate_answers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    question_key text NOT NULL,
    normalized_question text,
    answer_type varchar(20) NOT NULL DEFAULT 'text'
        CHECK (answer_type IN ('text', 'boolean', 'select', 'number', 'date')),
    answer jsonb NOT NULL DEFAULT '{}',

    source varchar(20) NOT NULL DEFAULT 'user'
        CHECK (source IN ('user', 'profile', 'resume', 'generated')),
    confidence numeric NOT NULL DEFAULT 1.0,
    evidence jsonb,
    approved_by_user boolean NOT NULL DEFAULT false,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    UNIQUE (user_id, question_key)
);
CREATE INDEX candidate_answers_user_idx ON public.candidate_answers (user_id);

ALTER TABLE public.candidate_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidate_answers ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.candidate_profiles, public.candidate_answers FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.candidate_profiles, public.candidate_answers TO service_role;
CREATE POLICY candidate_profiles_service ON public.candidate_profiles TO service_role USING (true) WITH CHECK (true);
CREATE POLICY candidate_answers_service ON public.candidate_answers TO service_role USING (true) WITH CHECK (true);
