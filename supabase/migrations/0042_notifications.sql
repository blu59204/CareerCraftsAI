-- In-app notifications (the AppTopbar bell dropdown) plus the channel
-- preferences that gate them, matching the toggles already shipped in
-- Settings -> Notifications (previously local-only state with no backend).
CREATE TABLE public.notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    type varchar(40) NOT NULL,
    title varchar(200) NOT NULL,
    body text,
    link varchar(500),
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX notifications_user_created_idx
    ON public.notifications (user_id, created_at DESC);
CREATE INDEX notifications_user_unread_idx
    ON public.notifications (user_id) WHERE read_at IS NULL;

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.notifications FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.notifications TO service_role;
CREATE POLICY notifications_service ON public.notifications
    TO service_role USING (true) WITH CHECK (true);

ALTER TABLE public.user_preferences
    ADD COLUMN IF NOT EXISTS notify_email boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS notify_agent_alerts boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS notify_followup_reminders boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS notify_weekly_digest boolean NOT NULL DEFAULT false;

-- Safe downgrade: only removes what this migration introduced.
-- ALTER TABLE public.user_preferences
--     DROP COLUMN IF EXISTS notify_email,
--     DROP COLUMN IF EXISTS notify_agent_alerts,
--     DROP COLUMN IF EXISTS notify_followup_reminders,
--     DROP COLUMN IF EXISTS notify_weekly_digest;
-- DROP TABLE IF EXISTS public.notifications;
