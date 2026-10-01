-- Each member has at most one active model. The API already deactivates
-- the others when one is saved or activated; this makes it a guarantee.
-- Anyone left with several active rows keeps one (the table has no
-- timestamp, so the choice is arbitrary but deterministic).
UPDATE public.user_model_settings AS m
SET is_active = false
WHERE m.is_active
  AND EXISTS (
      SELECT 1 FROM public.user_model_settings AS newer
      WHERE newer.user_id = m.user_id
        AND newer.is_active
        AND newer.id > m.id
  );

CREATE UNIQUE INDEX IF NOT EXISTS user_model_settings_one_active
    ON public.user_model_settings (user_id)
    WHERE is_active;
