CREATE TABLE job_applications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  company TEXT NOT NULL,
  role TEXT NOT NULL,
  job_url TEXT,
  jd_text TEXT,
  match_score INTEGER CHECK (match_score BETWEEN 0 AND 100),
  resume_id UUID REFERENCES user_documents(id),
  cover_letter TEXT,
  status TEXT DEFAULT 'saved'
    CHECK (status IN ('saved','applied','viewed','interview','offer','rejected')),
  applied_at TIMESTAMPTZ,
  followup_day5 TIMESTAMPTZ,
  followup_day12 TIMESTAMPTZ,
  notes TEXT
);

CREATE INDEX idx_applications_user_id ON job_applications(user_id);
CREATE INDEX idx_applications_status ON job_applications(user_id, status);
