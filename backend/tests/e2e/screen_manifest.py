"""
screen_manifest.py — authoritative list of authenticated screens under `(app)`.

Used by live E2E smoke tests to assert every authenticated route renders
without bouncing to /login. Keep in sync with `frontend/src/app/(app)/**`.
"""
from __future__ import annotations

from typing import NamedTuple


class Screen(NamedTuple):
    path: str
    heading: str


AUTHENTICATED_SCREENS = [
    Screen("/onboarding", "Welcome"), Screen("/dashboard", "Dashboard"),
    Screen("/agents", "Agent"), Screen("/jobs", "Find your next role"),
    Screen("/applications", "Application Tracker"), Screen("/resume", "Resume"),
    Screen("/cover-letter", "Cover Letter"), Screen("/linkedin", "LinkedIn"),
    Screen("/linkedin/outreach", "LinkedIn Outreach"), Screen("/email", "AI-powered outreach"),
    Screen("/interview", "Interview Coach"), Screen("/interview-prep", "Practice makes perfect"),
    Screen("/company", "Company"), Screen("/salary", "Salary"),
    Screen("/leads", "Recruiter Contacts"), Screen("/settings", "Account Settings"),
    Screen("/settings/account", "Account Settings"), Screen("/settings/profile", "Job"),
    Screen("/settings/integrations", "Integrations"), Screen("/settings/models", "Model Settings"),
]
