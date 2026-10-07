-- The auto-apply rule acts only on jobs found after it was last switched on,
-- never the existing backlog. Members who already have it on start from now.
-- Rollback: ALTER TABLE public.user_preferences DROP COLUMN IF EXISTS auto_rule_enabled_at;
ALTER TABLE public.user_preferences
    ADD COLUMN IF NOT EXISTS auto_rule_enabled_at timestamptz;

UPDATE public.user_preferences
SET auto_rule_enabled_at = now()
WHERE auto_apply_enabled AND auto_rule_enabled_at IS NULL;
