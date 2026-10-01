-- The scheduled daily job search spends the member's own API key on browser
-- automation and LLM calls, so it now runs only for members who turn it on.
ALTER TABLE public.user_preferences
  ADD COLUMN IF NOT EXISTS daily_search_enabled boolean NOT NULL DEFAULT false;
