-- Provider-neutral Nango connection references. OAuth credentials remain in Nango.
CREATE TABLE public.integration_connections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    provider varchar(40) NOT NULL,
    provider_config_key varchar(100) NOT NULL,
    external_connection_id varchar(255) UNIQUE,
    status varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'connected', 'disconnected', 'error', 'revoked')),
    provider_metadata_enc text,
    connected_at timestamptz,
    last_synced_at timestamptz,
    disconnected_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_integration_connections_user_provider UNIQUE (user_id, provider)
);

CREATE INDEX integration_connections_user_provider_status_idx
    ON public.integration_connections (user_id, provider, status);

CREATE TABLE public.integration_webhook_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_hash varchar(64) NOT NULL UNIQUE,
    event_type varchar(40),
    external_connection_id varchar(255),
    status varchar(20) NOT NULL DEFAULT 'received',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX integration_webhook_events_connection_idx
    ON public.integration_webhook_events (external_connection_id);

ALTER TABLE public.integration_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.integration_webhook_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.integration_connections, public.integration_webhook_events FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.integration_connections, public.integration_webhook_events TO service_role;
CREATE POLICY integration_connections_service ON public.integration_connections
    TO service_role USING (true) WITH CHECK (true);
CREATE POLICY integration_webhook_events_service ON public.integration_webhook_events
    TO service_role USING (true) WITH CHECK (true);

-- Safe downgrade: only removes tables introduced by this migration.
-- DROP TABLE IF EXISTS public.integration_webhook_events;
-- DROP TABLE IF EXISTS public.integration_connections;
