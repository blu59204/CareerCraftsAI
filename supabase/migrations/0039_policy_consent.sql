-- Sign-up now requires a single checkbox agreeing to the Terms of Service
-- and Privacy Policy together; these two columns are the durable record of
-- that click (when, and which policy revision was current at the time).
-- NULL means the account predates this requirement — never backfilled with
-- a fabricated timestamp.
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS policy_accepted_at timestamptz,
    ADD COLUMN IF NOT EXISTS policy_version varchar(20);
