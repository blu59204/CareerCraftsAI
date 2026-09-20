# Nango Integration Gateway

CareerCraft exposes provider-neutral integration APIs backed by Nango when
`NANGO_ENABLED=true`. The backend alone reads `NANGO_SECRET_KEY`; browsers
receive only the short-lived Connect-session values returned by Nango.

## Configure Nango

Create the required Google Mail, Google Drive, Google Calendar, Microsoft
Outlook Mail, and Microsoft Outlook Calendar integrations in the target Nango
environment. Set their **integration unique keys** in one JSON environment
variable; these keys are deployment-specific and must not be copied from an
example project.

```dotenv
NANGO_ENABLED=true
NANGO_BASE_URL=https://api.nango.dev
NANGO_SECRET_KEY=server-only-environment-api-key
NANGO_WEBHOOK_SECRET=webhook-signing-key
NANGO_PROVIDER_CONFIG_KEYS={"gmail":"google-mail-prod","google_drive":"google-drive-prod","google_calendar":"google-calendar-prod","outlook_mail":"outlook-mail-prod","outlook_calendar":"outlook-calendar-prod"}
```

Set the Nango webhook URL to
`https://<api-host>/api/v1/integrations/webhooks/nango`. The endpoint verifies
Nango's documented `X-Nango-Hmac-Sha256` HMAC-SHA256 signature over the raw
body. It stores a deterministic event hash before processing, so duplicate
deliveries are harmless. Do not place the environment API key or webhook key
in any `NEXT_PUBLIC_*` variable.

Apply `supabase/migrations/0037_integration_connections.sql` before enabling
the feature. It adds local provider-neutral connection and webhook replay
ledgers only; it never copies OAuth access or refresh tokens out of Nango.

## API and browser flow

1. The authenticated client calls `POST /api/v1/integrations/connect-session`
   with a supported provider and same-origin return path.
2. The backend creates a Nango Connect session and records a local `pending`
   connection.
3. The client follows the returned short-lived `connect_link`.
4. Nango confirms the connection through the verified webhook. Clients refresh
   `GET /api/v1/integrations`; frontend callbacks alone never mark a connection
   as connected.

Supported provider IDs are `gmail`, `google_drive`, `google_calendar`,
`outlook_mail`, and `outlook_calendar`. The APIs never return provider tokens.

`NANGO_DIRECT_GOOGLE_FALLBACK_ENABLED=true` keeps the existing encrypted
Google OAuth path available during migration. Keep it enabled until existing
users have reconnected in Nango and production metrics show no fallback use.
It can then be removed in a dedicated migration release; do not remove legacy
credentials or force-disconnect users as part of enabling Nango.

## Rollback

Set `NANGO_ENABLED=false` and redeploy. Existing direct Google OAuth remains
available behind the fallback flag. The database migration is additive; retain
its connection records for audit and replay protection. If a database rollback
is required before the feature is used, the commented safe downgrade statements
in migration `0037` remove only the two Nango tables.

See the official [Nango Connect sessions documentation](https://docs.nango.dev/guides/platform/connect-sessions)
and [webhook verification documentation](https://docs.nango.dev/guides/platform/webhooks)
when creating or rotating Nango credentials.
