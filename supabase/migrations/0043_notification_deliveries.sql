-- Per-channel delivery ledger for notifications — the durable, queryable
-- dead-letter record Temporal itself doesn't keep. NotificationWorkflow
-- creates one row per additional channel (today: "email") and drives it
-- through pending -> sent, or -> dead once that channel's retry budget
-- (enforced by Temporal, not this table) is exhausted.
CREATE TABLE public.notification_deliveries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id uuid NOT NULL REFERENCES public.notifications(id) ON DELETE CASCADE,
    channel varchar(20) NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sent', 'dead')),
    attempts integer NOT NULL DEFAULT 0,
    last_error text,
    idempotency_key varchar(255),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX notification_deliveries_notification_idx
    ON public.notification_deliveries (notification_id);
-- Operator triage: "show me everything currently stuck or dead."
CREATE INDEX notification_deliveries_status_idx
    ON public.notification_deliveries (status) WHERE status != 'sent';

ALTER TABLE public.notification_deliveries ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.notification_deliveries FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.notification_deliveries TO service_role;
CREATE POLICY notification_deliveries_service ON public.notification_deliveries
    TO service_role USING (true) WITH CHECK (true);

-- Safe downgrade: only removes what this migration introduced.
-- DROP TABLE IF EXISTS public.notification_deliveries;
