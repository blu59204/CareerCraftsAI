-- "supabase_uid" was a leftover name from before auth moved to Clerk — the
-- column has held Clerk subject ids (e.g. "user_2abc...") for a long time.
-- RENAME COLUMN updates every dependent object (RLS policies, indexes, the
-- unique constraint) automatically, since Postgres stores those by attribute
-- number, not by the column's text name — no policy edits needed here.
ALTER TABLE public.users RENAME COLUMN supabase_uid TO clerk_user_id;
