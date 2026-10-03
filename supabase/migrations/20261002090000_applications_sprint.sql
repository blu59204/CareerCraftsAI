-- Applications list, auto-apply rules and resume preferences.
-- Additive only. Rollback (run by hand, in this order):
--   DROP TABLE IF EXISTS public.action_log;
--   DROP INDEX IF EXISTS public.user_documents_one_primary_resume;
--   DROP INDEX IF EXISTS public.idx_applications_user_found;
--   ALTER TABLE public.user_preferences
--       DROP COLUMN IF EXISTS auto_rule_min_match, DROP COLUMN IF EXISTS auto_rule_action,
--       DROP COLUMN IF EXISTS resume_template, DROP COLUMN IF EXISTS resume_page_target,
--       DROP COLUMN IF EXISTS resume_tailor_per_job, DROP COLUMN IF EXISTS resume_tone,
--       DROP COLUMN IF EXISTS resume_prefs_set_at;
--   ALTER TABLE public.job_applications
--       DROP COLUMN IF EXISTS found_at, DROP COLUMN IF EXISTS deleted_at,
--       DROP COLUMN IF EXISTS apply_state;

-- When the member first saw the role. Backfilled from the shared catalog's
-- first sighting, then the posting date, then the apply date, so existing rows
-- don't all read as "found today".
ALTER TABLE public.job_applications
    ADD COLUMN IF NOT EXISTS found_at timestamptz,
    ADD COLUMN IF NOT EXISTS deleted_at timestamptz,
    -- Assisted apply in the member's own browser: opened -> applied | failed.
    ADD COLUMN IF NOT EXISTS apply_state text
        CHECK (apply_state IN ('opened', 'applied', 'failed'));

UPDATE public.job_applications AS a
SET found_at = COALESCE(
    (SELECT c.first_seen_at FROM public.job_catalog AS c WHERE c.url = a.job_url),
    a.posted_at,
    a.applied_at,
    now()
)
WHERE a.found_at IS NULL;

ALTER TABLE public.job_applications
    ALTER COLUMN found_at SET DEFAULT now(),
    ALTER COLUMN found_at SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_applications_user_found
    ON public.job_applications (user_id, found_at DESC)
    WHERE deleted_at IS NULL;

-- One auto-apply rule per member: new saved job >= threshold -> action.
-- auto_apply_enabled (existing) is the pause switch.
-- Resume preferences are asked once on first auto-apply (resume_prefs_set_at
-- NULL means "not asked yet") and editable in Settings.
ALTER TABLE public.user_preferences
    ADD COLUMN IF NOT EXISTS auto_rule_min_match smallint NOT NULL DEFAULT 70
        CHECK (auto_rule_min_match BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS auto_rule_action text NOT NULL DEFAULT 'apply'
        CHECK (auto_rule_action IN ('apply', 'outreach', 'both', 'notify')),
    ADD COLUMN IF NOT EXISTS resume_template text,
    ADD COLUMN IF NOT EXISTS resume_page_target smallint NOT NULL DEFAULT 2
        CHECK (resume_page_target IN (1, 2)),
    ADD COLUMN IF NOT EXISTS resume_tailor_per_job boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS resume_tone text NOT NULL DEFAULT 'professional',
    ADD COLUMN IF NOT EXISTS resume_prefs_set_at timestamptz;

-- Every auto-apply / outreach / delete action a member or rule takes.
CREATE TABLE IF NOT EXISTS public.action_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    job_application_id uuid REFERENCES public.job_applications(id) ON DELETE SET NULL,
    action text NOT NULL,
    source text NOT NULL DEFAULT 'user' CHECK (source IN ('user', 'rule')),
    detail jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_action_log_user ON public.action_log (user_id, created_at DESC);
ALTER TABLE public.action_log ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.action_log FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.action_log TO service_role;
CREATE POLICY action_log_service ON public.action_log TO service_role USING (true) WITH CHECK (true);

-- Exactly one active (primary) resume per member. Keep the most recently
-- embedded one if several (the table has no created_at).
UPDATE public.user_documents AS d
SET is_primary = false
WHERE d.is_primary AND d.doc_type = 'resume'
  AND EXISTS (
      SELECT 1 FROM public.user_documents AS newer
      WHERE newer.user_id = d.user_id AND newer.doc_type = 'resume' AND newer.is_primary
        AND newer.id <> d.id
        AND (COALESCE(newer.embedded_at, '-infinity'), newer.id)
            > (COALESCE(d.embedded_at, '-infinity'), d.id)
  );
CREATE UNIQUE INDEX IF NOT EXISTS user_documents_one_primary_resume
    ON public.user_documents (user_id)
    WHERE is_primary AND doc_type = 'resume';
