"""
test_live_user_journeys.py — authenticated browser journeys against a live,
deployed CareerCraft AI stack.

These tests exercise real screens end-to-end (no mocks) to catch
frontend/backend contract drift that unit tests can't see — e.g. a page still
calling a synchronous endpoint for an agent that now runs 60-120s server-side.

Requires RUN_LIVE_E2E=1 plus TEST_JWT, TEST_EMAIL, TEST_PASSWORD, WEB_URL,
API_URL (see conftest.py's `_auth_state` fixture, which skips otherwise).
"""
from __future__ import annotations

import os

from playwright.sync_api import expect

WEB_URL = os.getenv("WEB_URL", "http://localhost:3000")


def test_company_action_outlives_http_timeout(authenticated_page):
    page = authenticated_page
    page.goto(f"{WEB_URL}/company")
    page.get_by_placeholder("Enter company name...").fill("Example Corp")
    page.get_by_role("button", name="Research").click()
    expect(page.get_by_text("backend not connected")).to_have_count(0)
    expect(page.get_by_text("Overview")).to_be_visible(timeout=180_000)
