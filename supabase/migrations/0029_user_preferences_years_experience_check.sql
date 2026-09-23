-- Enforce sane experience-year values for future writes.
-- Existing rows are not validated here so deployments with legacy data do not fail.

ALTER TABLE public.user_preferences
    DROP CONSTRAINT IF EXISTS user_preferences_years_experience_check;

ALTER TABLE public.user_preferences
    ADD CONSTRAINT user_preferences_years_experience_check
    CHECK (
        years_experience IS NULL OR (years_experience >= 0 AND years_experience <= 60)
    )
    NOT VALID;
