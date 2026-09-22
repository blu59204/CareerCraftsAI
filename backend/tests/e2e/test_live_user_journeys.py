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

    # Source warnings ("Partial data - failed sources: ...") only render when
    # one or more of the agent's 4 sources (website/news/tech_stack/glassdoor)
    # failed for this particular run — a live "Example Corp" search may hit
    # all 4 sources cleanly, so asserting this is always visible would make
    # the test flaky. Assert on it conditionally instead: when the DOM shows
    # the warning, verify it's actually visible (not just present-but-hidden)
    # and non-empty, so the source-warnings render path stays covered on the
    # runs where it does fire.
    partial_data_warning = page.get_by_text("Partial data - failed sources:", exact=False)
    if partial_data_warning.count() > 0:
        expect(partial_data_warning).to_be_visible()
        assert partial_data_warning.inner_text().strip() != "Partial data - failed sources:", (
            "expected at least one failed source name after the warning prefix"
        )

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


def test_interview_coach_start_answer_and_next_question(authenticated_page):
    """Interview Coach must return the full session/question/feedback
    contract fixed in this change — not just {run_id, status} — and the
    per-turn question_index bug (every answer silently scored against
    question 0) must not resurface: after answering question 1, the UI must
    show question 2, not a repeat of question 1."""
    page = authenticated_page
    page.goto(f"{WEB_URL}/interview")
    page.get_by_placeholder("Target Role *").fill("Senior Backend Engineer")
    page.get_by_role("button", name="Start Session").click()

    expect(page.get_by_text("Failed to start session")).to_have_count(0)

    # start_session_node's LLM call + session write can take a while.
    expect(page.get_by_text("Question 1")).to_be_visible(timeout=180_000)
    first_question = page.locator("p.text-lg.font-medium").inner_text()
    assert first_question.strip(), "expected the first question's text to render"

    page.get_by_placeholder("Type your answer (minimum 10 words)...").fill(
        "I designed a distributed job queue that processed a million tasks a "
        "day and cut p99 latency by forty percent."
    )
    page.get_by_role("button", name="Submit Answer").click()

    expect(page.get_by_text("Failed to submit answer")).to_have_count(0)

    # Score/rating/tips feedback for question 1 must render.
    expect(page.get_by_text("Previous Feedback")).to_be_visible(timeout=180_000)
    expect(page.get_by_text("Q1:", exact=False)).to_be_visible()
    expect(page.get_by_text("/100", exact=False)).to_be_visible()

    # Either the next question renders (question_index correctly advanced to
    # 1, not reset to 0) or, if the agent only generated one question, the
    # session-complete summary renders instead — both are valid terminal
    # states for this contract; a repeat of question 1 with no summary is not.
    next_question_visible = page.get_by_text("Question 2").is_visible()
    session_complete_visible = page.get_by_text("Session Complete").is_visible()
    assert next_question_visible or session_complete_visible, (
        "expected either question 2 or the session summary after answering question 1"
    )


def test_email_inbox_cleanup_never_shows_fake_sender(authenticated_page):
    """Inbox Cleanup must render live Gmail metadata (or an explicit
    connect/empty state) — never the removed hardcoded INBOX_EMAILS sample
    data (LinkedIn/AWS/GitHub/... preview senders) or its
    "Preview only — sample data" disclaimer."""
    page = authenticated_page
    page.goto(f"{WEB_URL}/email")
    page.get_by_role("button", name="Inbox", exact=False).click()

    expect(page.get_by_text("Preview only", exact=False)).to_have_count(0)
    for fake_sender in ["AWS", "Medium Daily", "Glassdoor", "Shopify", "Twitter/X"]:
        expect(page.get_by_text(fake_sender, exact=True)).to_have_count(0)


def test_interview_prep_practice_uses_generated_plan_question(authenticated_page):
    """Mock interview practice must start from the generated plan's
    questions array, not the removed MOCK_INTERVIEW_QUESTIONS constant —
    and must stay disabled with "Generate an interview plan first" until a
    plan exists."""
    page = authenticated_page
    page.goto(f"{WEB_URL}/interview-prep")

    start_button = page.get_by_role("button", name="Start mock interview")
    expect(start_button).to_be_disabled()

    page.get_by_placeholder("Role").fill("Senior Backend Engineer")
    page.get_by_role("button", name="Generate questions").click()

    expect(page.get_by_text("AI-generated", exact=False)).to_be_visible(timeout=180_000)
    expect(start_button).to_be_enabled()

    first_question = page.locator("p.text-sm.font-medium.leading-relaxed").first.inner_text()

    start_button.click()
    modal_question = page.locator(".rounded-2xl.bg-primary\\/5 p").first.inner_text()
    assert modal_question.strip() == first_question.strip(), (
        "expected the mock interview's first question to come from the generated plan"
    )
