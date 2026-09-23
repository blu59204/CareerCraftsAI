-- Migration: 0031_user_preferences_prefer_live_browser
-- Adds a per-user flag to opt in to visible Chromium for autonomous job
-- search and apply.  When True, POST /api/v1/jobs/search and
-- /api/v1/jobs/applications/{id}/prepare-apply will run a visible browser
-- (headless=False) and stream screenshots to the UI over SSE.  When False
-- (default), the headless Remotive/Arbeitnow/Jobicy/JobSpy waterfall runs
-- — faster, no CAPTCHAs, but invisible to the user.

ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS prefer_live_browser BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN user_preferences.prefer_live_browser IS
    'When true, autonomous job search + apply open a visible Chromium and stream browser_frame SSE events to the UI.  Always overridable per-request.';
