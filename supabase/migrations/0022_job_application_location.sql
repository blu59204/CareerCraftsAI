-- Persist searched job location so saved jobs can be filtered by user-selected location.
ALTER TABLE job_applications
  ADD COLUMN IF NOT EXISTS location TEXT;
