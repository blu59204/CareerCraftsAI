CREATE TABLE user_model_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  api_key_enc TEXT,
  model_name TEXT,
  ollama_url TEXT,
  is_active BOOLEAN DEFAULT true
);

CREATE INDEX idx_model_settings_user_id ON user_model_settings(user_id);
