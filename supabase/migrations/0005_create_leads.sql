CREATE TABLE leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  name TEXT,
  email TEXT,
  company TEXT,
  linkedin_url TEXT,
  status TEXT DEFAULT 'cold' CHECK (status IN ('cold','warm','replied','converted')),
  last_contact TIMESTAMPTZ,
  notes TEXT
);
CREATE INDEX idx_leads_user_id ON leads(user_id);
