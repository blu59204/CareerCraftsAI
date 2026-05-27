-- memory/schemas.sql
-- Run via: psql $DATABASE_URL -f schemas.sql
-- Or apply through Supabase migrations.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS user_memories (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES users(id) ON DELETE CASCADE,
  memory_type   TEXT NOT NULL CHECK (memory_type IN ('preference','fact','outcome','blacklist','skill','style')),
  content       TEXT NOT NULL,
  embedding     vector(1536),
  source_agent  TEXT,
  confidence    FLOAT DEFAULT 1.0,
  times_used    INTEGER DEFAULT 0,
  is_active     BOOLEAN DEFAULT true,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_episodes (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES users(id) ON DELETE CASCADE,
  agent_type    TEXT NOT NULL,
  summary       TEXT,
  input         JSONB,
  output        JSONB,
  outcome       TEXT CHECK (outcome IN ('success','failure','pending','skipped')),
  embedding     vector(1536),
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_learnings (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_type     TEXT NOT NULL,
  learning       TEXT NOT NULL,
  evidence_count INTEGER DEFAULT 1,
  success_rate   FLOAT DEFAULT 1.0,
  last_applied   TIMESTAMPTZ,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memory_access_log (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id),
  query       TEXT,
  results     JSONB,
  agent_type  TEXT,
  accessed_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW indexes for fast approximate nearest-neighbour search (cosine distance)
CREATE INDEX IF NOT EXISTS user_memories_hnsw ON user_memories USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS agent_episodes_hnsw ON agent_episodes USING hnsw (embedding vector_cosine_ops);

-- Supporting B-tree index for filtered lookups
CREATE INDEX IF NOT EXISTS user_memories_uid ON user_memories (user_id, memory_type, is_active);
