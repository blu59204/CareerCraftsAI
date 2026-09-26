-- Account deletion is a 15-day grace period, not instant: requesting it sets
-- deletion_requested_at/deletion_scheduled_for, and a maintenance sweep
-- hard-deletes once deletion_scheduled_for has passed. Cancelling (by the
-- user clicking "Cancel deletion", or automatically on their next visit
-- after leaving) clears both and starts a 30-day deletion_cooldown_until
-- during which they can't request deletion again.
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS deletion_requested_at timestamptz,
    ADD COLUMN IF NOT EXISTS deletion_scheduled_for timestamptz,
    ADD COLUMN IF NOT EXISTS deletion_cooldown_until timestamptz;
