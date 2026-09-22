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


def test_company_research_renders_full_intel(authenticated_page):
    """Company Research must migrate off the dead GET /company/research?name=
    route and the 30s-vs-120s timeout mismatch on POST /company/research, and
    render the company_research agent's real terminal output — not a
    "backend not connected" fallback caused by the broken contract."""
    page = authenticated_page
    page.goto(f"{WEB_URL}/company")
    page.get_by_placeholder("Enter company name...").fill("Example Corp")
    page.get_by_role("button", name="Research").click()

    expect(page.get_by_text("backend not connected")).to_have_count(0)
    expect(page.get_by_text("Research failed")).to_have_count(0)

    # Terminal sections the company_research agent's output must populate.
    expect(page.get_by_text("Overview")).to_be_visible(timeout=180_000)
    expect(page.get_by_text("Culture")).to_be_visible()
    expect(page.get_by_text("Recent News")).to_be_visible()
    expect(page.get_by_text("Tech Stack")).to_be_visible()
    expect(page.get_by_text("Glassdoor Sentiment")).to_be_visible()
    # Timestamp rendered from the agent's researched_at field.
    expect(page.get_by_text("Last researched:", exact=False)).to_be_visible()

    # Force Refresh must exist and re-run with force_refresh: true — it must
    # not silently reuse stale data forever.
    expect(page.get_by_role("button", name="Force Refresh")).to_be_visible()


def test_salary_report_awaits_approval(authenticated_page):
    """Salary must migrate off POST /salary/report + GET /salary/report/{id}
    (same 30s-vs-120s timeout mismatch as Company) and instead poll the
    generic agent run until awaiting_approval, rendering non-zero percentiles
    and a negotiation script — then leave the HITL gate untouched. The live
    test must never click Approve; that is a separate, deliberate action."""
    page = authenticated_page
    page.goto(f"{WEB_URL}/salary")
    page.get_by_placeholder("Role *").fill("Senior Software Engineer")
    page.get_by_placeholder("Location (optional)").fill("Remote")
    page.get_by_role("button", name="Generate Report").click()

    expect(page.get_by_text("backend not connected")).to_have_count(0)
    expect(page.get_by_text("Failed to generate report")).to_have_count(0)

    expect(page.get_by_text("Market Percentiles")).to_be_visible(timeout=180_000)

    # p25/p50/p75 values must be non-zero (a real market benchmark, not an
    # empty/failed contract silently mapped to zeros).
    percentile_values = page.locator("span.font-mono").all_text_contents()
    assert percentile_values, "expected p25/p50/p75 values to render"
    assert all(v not in ("$0", "") for v in percentile_values), (
        f"expected non-zero salary percentiles, got {percentile_values}"
    )

    expect(page.get_by_text("Negotiation Script")).to_be_visible()

    # HITL gate: the run must still be awaiting_approval. Approve & Discard
    # are visible and enabled, but the test must not click either — clicking
    # Approve would send/finalize the negotiation script for real.
    approve_button = page.get_by_role("button", name="Approve & Use")
    expect(approve_button).to_be_visible()
    expect(approve_button).to_be_enabled()
    expect(page.get_by_role("button", name="Discard")).to_be_visible()
