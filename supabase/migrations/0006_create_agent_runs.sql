CREATE TABLE agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  agent_type TEXT NOT NULL,
  status TEXT DEFAULT 'running'
    CHECK (status IN ('running','awaiting_approval','completed','failed')),
  input JSONB,
  output JSONB,
  tokens_used INTEGER,
  duration_ms INTEGER,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);
CREATE INDEX idx_agent_runs_user_id ON agent_runs(user_id);
CREATE INDEX idx_agent_runs_status ON agent_runs(status);
