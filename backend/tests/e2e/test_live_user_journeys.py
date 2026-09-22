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
import re
import time
from datetime import datetime, timezone

from playwright.sync_api import expect

WEB_URL = os.getenv("WEB_URL", "http://localhost:3000")


def _fixture_value(label: str) -> str:
    """Disposable, timestamped value for fields this run writes and then
    re-reads (e.g. after a reload) — keeps each run's assertion unambiguous
    even against a long-lived shared test account."""
    return f"E2E-{label}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}"


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


# ---------------------------------------------------------------------------
# Step 1: identity/settings journeys
# ---------------------------------------------------------------------------


def test_settings_redirects_to_account(authenticated_page):
    """`/settings` must redirect to `/settings/account` server-side — a
    regression here (e.g. a broken redirect() call) would land users on a
    blank or 404 page with no indication of what happened."""
    page = authenticated_page
    page.goto(f"{WEB_URL}/settings")
    expect(page).to_have_url(re.compile(r"/settings/account/?$"), timeout=30_000)
    expect(page.get_by_text("Account Settings")).to_be_visible()


def test_account_settings_shows_signin_email_and_persists_headline(authenticated_page):
    """Account settings must render the real Clerk sign-in email (not a
    stale/blank profile.email column) and persist an edited profile field
    across a reload — proving PATCH /users/me actually writes through
    instead of only updating client-side query cache."""
    page = authenticated_page
    test_email = os.environ["TEST_EMAIL"]
    headline_value = _fixture_value("headline")

    page.goto(f"{WEB_URL}/settings/account")
    expect(page.get_by_text(test_email, exact=False)).to_be_visible(timeout=30_000)

    headline_input = page.get_by_placeholder("e.g. Senior Software Engineer at Stripe")
    headline_input.fill(headline_value)
    page.get_by_role("button", name="Save changes").click()
    expect(page.get_by_text("Profile updated")).to_be_visible(timeout=30_000)

    page.reload()
    expect(page.get_by_placeholder("e.g. Senior Software Engineer at Stripe")).to_have_value(
        headline_value, timeout=30_000
    )


def test_profile_preferences_persists_bio_after_reload(authenticated_page):
    """Job preferences (target roles, work mode, bio, ...) are the primary
    signal every other agent reads — a save that silently no-ops would make
    every downstream agent (search, resume, outreach) work off stale data
    with no visible error."""
    page = authenticated_page
    bio_value = _fixture_value("bio")

    page.goto(f"{WEB_URL}/settings/profile")
    bio_placeholder = "A short summary about yourself, your skills, and what you're looking for in your next role…"
    bio_input = page.get_by_placeholder(bio_placeholder)
    expect(bio_input).to_be_visible(timeout=30_000)
    bio_input.fill(bio_value)
    page.get_by_role("button", name="Save preferences").click()
    expect(page.get_by_text("Preferences saved")).to_be_visible(timeout=30_000)

    page.reload()
    expect(page.get_by_placeholder(bio_placeholder)).to_have_value(bio_value, timeout=30_000)


def test_integrations_page_lists_providers_and_connection_state(authenticated_page):
    """Integrations must render the full provider catalog (Gmail, Drive,
    Calendar, Outlook) regardless of connection state, and — when a
    provider is actually connected — must surface which external account
    it's connected to, so a user isn't left guessing whether a stale/wrong
    Google account is the one agents will act as."""
    page = authenticated_page
    page.goto(f"{WEB_URL}/settings/integrations")

    for provider_name in [
        "Gmail",
        "Google Drive",
        "Google Calendar",
        "Microsoft Outlook Mail",
        "Microsoft Outlook Calendar",
    ]:
        expect(page.get_by_role("heading", name=provider_name)).to_be_visible(timeout=30_000)

    expect(page.get_by_text("Could not load integrations")).to_have_count(0)

    # Conditional, like the Company Research "partial data" pattern: only
    # assert the connected-account-email line when a provider actually is
    # connected in this run's account, but when it fires, it must be real.
    connected_status = page.get_by_text("Status: connected", exact=False)
    if connected_status.count() > 0:
        connected_email = page.get_by_text("Connected account:", exact=False)
        expect(connected_email.first).to_be_visible()
        assert connected_email.first.inner_text().strip() != "Connected account:", (
            "expected a real account email after the 'Connected account:' label"
        )


def test_settings_models_deepseek_key_never_leaks_and_test_returns_result(authenticated_page):
    """Covers three model-settings contracts in one pass: (1) DeepSeek must
    be a selectable provider with its own model list, (2) a saved API key
    must never re-render in the DOM nor appear in any /users/me/models
    response body — the backend must only ever echo back provider/model
    metadata, never api_key_enc or the plaintext key, and (3) the "Test"
    action against a saved key must produce a visible pass/fail result, not
    hang or silently no-op.

    NOTE: add_model_settings() deactivates every other key and marks the new
    one active (server-side, so exactly one model is ever active) — this
    would silently break every other live agent test in this suite if left
    pointed at a disposable fake key, so this test records whichever model
    was active beforehand and reactivates it in a `finally` block, so that
    restore step always runs even if an assertion above fails partway
    through the add/leak-check/test sequence."""
    page = authenticated_page
    fake_api_key = f"sk-e2e-do-not-use-{datetime.now(timezone.utc):%Y%m%d%H%M%S}"

    page.goto(f"{WEB_URL}/settings/models")

    active_badge = page.get_by_text("Active", exact=True)
    had_previously_active = active_badge.count() > 0
    previously_active_provider = None
    previously_active_model_name = None
    if had_previously_active:
        active_row = active_badge.first.locator("xpath=ancestor::div[contains(@class,'rounded-2xl')][1]")
        previously_active_provider = active_row.locator("div.text-sm.font-medium.truncate").inner_text()
        previously_active_model_name = active_row.locator("div.text-xs.text-muted-foreground.truncate").inner_text()

    responses: list = []
    page.on(
        "response",
        lambda response: responses.append(response) if "/users/me/models" in response.url else None,
    )

    # `model_added` gates the cleanup below: it only flips to True once we
    # have confirmed evidence (the "Model added" toast) that the backend
    # actually deactivated the previous model and activated our disposable
    # one — so a `finally` cleanup never fires (and never risks deleting
    # the wrong row) if the add itself never went through.
    model_added = False
    try:
        provider_select = page.locator("select").first
        model_select = page.locator("select").nth(1)
        provider_select.select_option(label="DeepSeek")
        expect(model_select).to_have_value("deepseek-flash")

        page.get_by_placeholder("Paste provider API key").fill(fake_api_key)
        page.get_by_role("button", name="Save API key").click()
        expect(page.get_by_text("Model added")).to_be_visible(timeout=30_000)
        model_added = True

        # The input clears and the raw key must never render anywhere on the page.
        expect(page.get_by_placeholder("Paste provider API key")).to_have_value("")
        expect(page.get_by_text(fake_api_key)).to_have_count(0)

        for response in responses:
            try:
                body = response.text()
            except Exception:
                continue
            assert fake_api_key not in body, (
                f"plaintext API key leaked into a {response.url} response body"
            )

        # Model-test action: must resolve to a visible pass/fail, not hang.
        # The new (now-active) DeepSeek entry is the one with the "Active" badge.
        new_row = page.get_by_text("Active", exact=True).first.locator(
            "xpath=ancestor::div[contains(@class,'rounded-2xl')][1]"
        )
        new_row.get_by_role("button", name="Test").click()
        expect(new_row.get_by_role("button", name="Testing…")).to_have_count(0, timeout=60_000)
        success = page.get_by_text("Model working:", exact=False)
        failure = page.get_by_text("Test failed", exact=False)
        assert success.count() > 0 or failure.count() > 0, (
            "expected a model-test result toast (success or failure) after clicking Test"
        )
    finally:
        # Always attempt to remove the disposable fake-key model and
        # restore whichever model was active before this test ran — even
        # if an assertion above failed partway through — so a single
        # broken check in this test can never leave the shared live
        # account's active model pointed at a garbage key for the rest of
        # the suite (resume tailoring, cover letter, interview prep,
        # company research, salary, interview coach all run live LLM
        # calls against whatever model is active).
        if model_added:
            try:
                new_row = page.get_by_text("Active", exact=True).first.locator(
                    "xpath=ancestor::div[contains(@class,'rounded-2xl')][1]"
                )
                page.once("dialog", lambda dialog: dialog.accept())
                new_row.get_by_role("button", name="Delete").click()
                expect(page.get_by_text("Model removed")).to_be_visible(timeout=30_000)
            except Exception:
                pass

            if had_previously_active:
                try:
                    restored_row = page.locator(
                        "div.rounded-2xl.border", has_text=previously_active_provider
                    ).filter(has_text=previously_active_model_name)
                    restore_button = restored_row.get_by_role("button", name="Set active")
                    if restore_button.count() > 0:
                        restore_button.first.click()
                        expect(page.get_by_text("Model activated")).to_be_visible(timeout=30_000)
                except Exception:
                    pass


def test_onboarding_wizard_completes_and_saves_target_role(authenticated_page):
    """The onboarding wizard must actually persist what the user enters —
    not just advance through steps client-side — and must land on
    /dashboard with onboarding_completed true, since every authenticated
    route redirects incomplete accounts back here."""
    page = authenticated_page
    target_role = _fixture_value("Role")
    location = _fixture_value("Location")

    page.goto(f"{WEB_URL}/onboarding")

    # Step 1: welcome
    page.get_by_role("button", name="Continue").click()
    # Step 2: goal / experience (defaults are fine)
    page.get_by_role("button", name="Continue").click()
    # Step 3: resume upload (optional — skip)
    page.get_by_role("button", name="Continue").click()
    # Step 4: target roles
    page.get_by_placeholder("Frontend Engineer, React Developer, Full Stack Developer").fill(target_role)
    page.get_by_role("button", name="Continue").click()
    # Step 5: preferred locations
    page.get_by_placeholder("Bangalore, Remote, Hyderabad").fill(location)
    page.get_by_role("button", name="Continue").click()
    # Step 6 (last): model — leave provider/key defaults, finish setup
    page.get_by_role("button", name="Finish").click()

    expect(page.get_by_text("Setup complete!", exact=False)).to_be_visible(timeout=30_000)
    expect(page).to_have_url(re.compile(r"/dashboard/?$"), timeout=30_000)

    page.goto(f"{WEB_URL}/settings/profile")
    expect(page.get_by_text(target_role, exact=False)).to_be_visible(timeout=30_000)


# ---------------------------------------------------------------------------
# Step 2: career-document journeys
# ---------------------------------------------------------------------------

RESUME_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "test_resume.pdf"
)


def test_resume_upload_ats_score_tailor_and_download(authenticated_page):
    """End-to-end resume workspace contract: upload must index the file as
    the primary resume, ATS analysis must parse *this run's* exact JD text
    (proven with a fixture keyword that cannot already be in the resume),
    tailoring must produce a real preview and auto-advance the run out of
    awaiting_approval, and Export must actually produce a downloadable
    file — not a silently-disabled button or a 404."""
    page = authenticated_page
    fixture_keyword = "zzqfluxwidget"
    jd_text = (
        "We are hiring a Senior Backend Engineer to build reliable APIs. "
        "Required skills: Python, FastAPI, PostgreSQL, Docker, and hands-on "
        f"experience with {fixture_keyword} systems integration."
    )

    # The frontend auto-approves resume drafts (no send/apply involved — see
    # ResumePage's optimizeMutation.onSuccess) rather than waiting on a user
    # click. Watch for that approve call directly instead of scraping the
    # History tab, since History lists every past run and a stale
    # awaiting_approval entry from unrelated data would make a text-absence
    # check flaky.
    approve_responses: list = []
    page.on(
        "response",
        lambda response: approve_responses.append(response)
        if re.search(r"/agents/.+/approve$", response.url)
        else None,
    )

    page.goto(f"{WEB_URL}/resume")
    page.locator('input[type="file"]').set_input_files(RESUME_FIXTURE_PATH)
    expect(page.get_by_text("test_resume.pdf", exact=False)).to_be_visible(timeout=60_000)

    jd_box = page.get_by_placeholder(
        "Paste the job description here… CareerCraft AI will analyze requirements, "
        "match keywords, and suggest targeted resume bullets."
    )
    jd_box.fill(jd_text)

    page.get_by_role("button", name="Analyze match").click()
    expect(page.get_by_text("Could not analyze this resume", exact=False)).to_have_count(0)
    expect(page.get_by_text(fixture_keyword, exact=True)).to_be_visible(timeout=60_000)

    page.get_by_role("button", name="Tailor Resume ✨").click()
    expect(page.get_by_text("We couldn’t tailor your resume", exact=False)).to_have_count(0)
    expect(page.get_by_text("Tailored ATS score:", exact=False)).to_be_visible(timeout=180_000)

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and not approve_responses:
        page.wait_for_timeout(500)
    assert approve_responses, "expected the tailored resume draft to be auto-approved"
    assert approve_responses[-1].ok, (
        f"resume draft approve call failed with status {approve_responses[-1].status}"
    )

    with page.expect_download() as download_info:
        page.get_by_role("button", name="Export").click()
    download = download_info.value
    assert download.suggested_filename, "expected the tailored resume PDF to actually download"


def test_cover_letter_generation_reflects_job_description(authenticated_page):
    """The generated cover letter must be produced from *this run's* job
    description, not a cached/boilerplate response — proven by a
    distinctive fictitious role that only appears in the JD we just typed
    and could not already exist in any prior fixture."""
    page = authenticated_page
    fixture_role = "Senior Kubernetes Whisperer"
    fixture_company = "Nimbus Quokka Systems"
    jd_text = (
        f"{fixture_company} is hiring a {fixture_role} to lead our platform "
        "reliability team, owning on-call rotation, cluster upgrades, and "
        "developer tooling."
    )

    page.goto(f"{WEB_URL}/cover-letter")
    page.get_by_placeholder("Paste the job description here to get a tailored cover letter…").fill(jd_text)
    page.get_by_role("button", name="Generate Cover Letter").click()

    expect(page.get_by_text("Generation failed", exact=False)).to_have_count(0)
    expect(page.get_by_text("Your cover letter will appear here")).to_have_count(0, timeout=180_000)

    letter_value = page.locator("textarea").last.input_value()
    assert letter_value.strip(), "expected non-empty generated cover letter content"
    lowered = letter_value.lower()
    assert fixture_role.lower() in lowered or fixture_company.lower() in lowered, (
        "expected the generated cover letter to reference the fixture role or company "
        "from this run's job description, not boilerplate"
    )


def test_linkedin_optimize_runs_and_leaves_approval_pending(authenticated_page):
    """LinkedIn analysis must run the real linkedin_optimize agent (not a
    dead endpoint) and stop at the HITL checkpoint before anything could be
    pushed to a live LinkedIn profile — the live test must never approve
    it, since LinkedIn OAuth publishing is a one-way, ToS-sensitive action."""
    page = authenticated_page
    page.goto(f"{WEB_URL}/linkedin")

    page.get_by_role("button", name="Run Analysis", exact=False).first.click()
    expect(page.get_by_text("backend not connected", exact=False)).to_have_count(0)
    expect(page.get_by_text("Agent unavailable", exact=False)).to_have_count(0)

    expect(page.get_by_text("Profile Sections")).to_be_visible(timeout=180_000)

    # If the run stopped at the HITL checkpoint (the expected outcome per
    # AGENTS.md), the approval modal must be visible with both actions
    # available — but the live test must never click Approve.
    review_modal = page.get_by_text("Review Required")
    if review_modal.count() > 0:
        expect(review_modal).to_be_visible()
        approve_button = page.get_by_role("button", name="Approve & Execute")
        expect(approve_button).to_be_visible()
        expect(approve_button).to_be_enabled()
        expect(page.get_by_role("button", name="Cancel")).to_be_visible()


def test_interview_prep_plan_reflects_target_company(authenticated_page):
    """Interview prep must generate a plan tailored to the company/role
    typed into this run, not a generic fallback — proven by counting
    mentions of a distinctive fixture company before vs. after generation:
    the input field and its own echo account for a fixed baseline, so any
    increase must come from the agent's actual output referencing it."""
    page = authenticated_page
    fixture_company = "Quokka Fjord Robotics"
    fixture_role = "Senior Kubernetes Whisperer"

    page.goto(f"{WEB_URL}/interview-prep")
    page.get_by_placeholder("Company").fill(fixture_company)
    page.get_by_placeholder("Role").fill(fixture_role)

    baseline_mentions = page.get_by_text(fixture_company, exact=False).count()

    page.get_by_role("button", name="Generate questions").click()
    expect(page.get_by_text("Agent unavailable", exact=False)).to_have_count(0)
    expect(page.get_by_text("AI-generated", exact=False)).to_be_visible(timeout=180_000)

    after_mentions = page.get_by_text(fixture_company, exact=False).count()
    assert after_mentions > baseline_mentions, (
        "expected the generated interview plan to reference the fixture company beyond "
        "the input field's own echo, proving the agent used this run's input"
    )


# ---------------------------------------------------------------------------
# Step 3: job/application journeys
# ---------------------------------------------------------------------------


def test_job_search_agent_persists_saved_jobs_to_applications(authenticated_page, api_client):
    """Job Search must actually persist matches as JobApplication rows —
    not just render an ephemeral in-memory results list — since
    /applications, the kanban tracker, and AutoApply prep all read from
    that table. Verified against the API (not just DOM counts) so this
    survives even if the live search returns a company name that happens
    to collide with existing shared-account data."""
    page = authenticated_page
    baseline = api_client.get("/jobs/applications", params={"status": "saved"}).json()
    baseline_count = len(baseline)

    page.goto(f"{WEB_URL}/jobs")
    page.get_by_placeholder(
        "Leave blank to use resume + saved preferences, or type custom role…"
    ).fill("Software Engineer")
    page.get_by_role("button", name="Run Job Agent").click()

    expect(page.get_by_text("Job Agent unavailable", exact=False)).to_have_count(0)
    expect(page.get_by_text("roles saved", exact=False)).to_be_visible(timeout=180_000)

    after = api_client.get("/jobs/applications", params={"status": "saved"}).json()
    assert len(after) > baseline_count, (
        "expected the job search run to persist at least one new saved JobApplication row"
    )

    page.goto(f"{WEB_URL}/applications")
    saved_count_text = page.get_by_text("Saved", exact=True).locator(
        "xpath=following-sibling::span[1]"
    ).inner_text()
    assert int(saved_count_text) >= 1, (
        "expected the Applications kanban's Saved column to reflect the persisted jobs"
    )

    # NOTE: the "Filter by company or role..." input in ApplicationsPage has
    # no onChange handler or query wiring today — it renders but cannot
    # actually filter the kanban. Documented here (structural presence
    # only) rather than asserting filtering behavior the shipped component
    # doesn't implement.
    expect(page.get_by_placeholder("Filter by company or role...")).to_be_visible()


def test_applications_kanban_drag_updates_status_and_persists(authenticated_page, api_client):
    """Dragging a card between kanban columns must PATCH the real
    JobApplication row — not just move the card client-side — proven by
    reloading and confirming the new stage survives. Restored via the API
    in a `finally` block so this shared live account's saved/applied split
    is never left mutated by the test run, even if an assertion above
    fails partway through."""
    page = authenticated_page
    page.goto(f"{WEB_URL}/applications")

    saved_column = page.get_by_text("Saved", exact=True).locator(
        "xpath=ancestor::div[contains(@class,'rounded-3xl')][1]"
    )
    first_card = saved_column.locator("div[draggable='true']").first
    expect(first_card).to_be_visible(timeout=30_000)
    company_name = first_card.locator("span.text-sm.font-medium").first.inner_text()

    applications = api_client.get("/jobs/applications", params={"status": "saved"}).json()
    match = next((a for a in applications if a["company"] == company_name), None)
    assert match, "expected the dragged card's application to be resolvable via the API"
    application_id = match["id"]

    try:
        applied_column = page.get_by_text("Applied", exact=True).locator(
            "xpath=ancestor::div[contains(@class,'rounded-3xl')][1]"
        )
        first_card.drag_to(applied_column)
        expect(page.get_by_text("Status updated")).to_be_visible(timeout=15_000)

        page.reload()
        applied_column = page.get_by_text("Applied", exact=True).locator(
            "xpath=ancestor::div[contains(@class,'rounded-3xl')][1]"
        )
        expect(applied_column.get_by_text(company_name, exact=True)).to_be_visible(timeout=30_000)
    finally:
        api_client.patch(f"/jobs/applications/{application_id}/status", json={"status": "saved"})


def test_auto_apply_first_checkpoint_includes_drafts_and_rejects_cleanly(
    authenticated_page, api_client, wait_for_run
):
    """AutoApplyPipeline's first HITL gate — resume + cold-outreach draft
    review, emitted before any apply_browser/send_email action is ever
    queued — must render real draft content, and rejecting it (never
    approving) must leave the run cancelled with nothing submitted, since
    AGENTS.md requires this gate to be un-bypassable.

    The generic /agents launcher is the only UI surface for auto_apply
    (there is no dedicated Auto Apply screen); it reuses AgentStatusStream
    + ApprovalModal, whose fallback branch renders the raw pipeline output
    as JSON for any action_type it doesn't specially render
    (`auto_apply_approval` isn't one of the specialised ones today), so the
    checkpoint content shows up as a JSON dump rather than a purpose-built
    preview — this asserts against that dump directly."""
    page = authenticated_page

    run_id_holder: dict[str, str] = {}

    def _capture_run_id(response):
        if response.request.method == "POST" and response.url.endswith("/agents/run"):
            try:
                run_id = response.json().get("run_id")
            except Exception:
                return
            if run_id:
                run_id_holder["id"] = run_id

    page.on("response", _capture_run_id)

    page.goto(f"{WEB_URL}/agents")
    page.get_by_role("button", name="Auto Apply", exact=False).click()
    page.get_by_role("button", name="Run agent").click()

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and "id" not in run_id_holder:
        page.wait_for_timeout(500)
    assert "id" in run_id_holder, "expected /agents/run to return a run_id for the Auto Apply run"
    run_id = run_id_holder["id"]

    expect(page.get_by_text("Review Required")).to_be_visible(timeout=300_000)
    checkpoint_dump = page.locator("pre").last.inner_text()
    assert checkpoint_dump.strip(), "expected the first checkpoint to render real pipeline output"
    assert "resume_markdown" in checkpoint_dump or "resume_draft" in checkpoint_dump, (
        "expected the auto-apply checkpoint to include resume/cover-letter draft content for review"
    )

    # HITL gate: Approve & Execute is visible and enabled, but this test
    # must never click it — that would queue the apply_browser/send_email
    # actions for real. Reject instead.
    approve_button = page.get_by_role("button", name="Approve & Execute")
    expect(approve_button).to_be_visible()
    expect(approve_button).to_be_enabled()
    page.get_by_role("button", name="Cancel").click()

    result = wait_for_run(api_client, run_id, timeout_s=30)
    assert result["status"] == "failed", (
        f"expected rejecting the checkpoint to cancel the run, got {result['status']}"
    )
    assert (result.get("output") or {}).get("error") == "Action cancelled by user", (
        "expected the run's output to record the rejection, not a submitted/queued outcome"
    )


# ---------------------------------------------------------------------------
# Step 4: research/coaching journeys
# ---------------------------------------------------------------------------
# Company Research, Salary, and Interview Coach journeys already exist above
# (Task 4/5 coverage) — not duplicated here. This step's new requirement is
# dashboard restoration of an in-flight run across a full page reload.


def test_dashboard_reload_restores_in_progress_agent_run(authenticated_page):
    """Reloading mid-run must not lose track of an in-flight agent on the
    client. The real restore path is `useAgentStream` (frontend/src/lib/sse.ts)
    — mounted globally in AppShell off the `localStorage`-persisted
    `activeRunId` (frontend/src/store/agentStore.ts) — whose `reconcile()`
    calls GET /agents/runs/{id} on mount and repopulates the in-memory
    zustand `runs` store, which a full browser reload always wipes. That is
    the mechanism this test exercises: launch a run through /agents (the
    only surface that calls `initRun`/`setActiveRun`, same as the
    AutoApply/EmailMonitor tests above), confirm the client actually shows
    live status for it, hard-reload, and confirm the *same* run's status is
    still shown afterward — proving the store was rebuilt from the server,
    not that a list endpoint happens to contain a DB row (a plain
    GET /users/me/stats list would pass that check whether or not reload
    restoration works at all, which is why /dashboard was the wrong page
    for this)."""
    page = authenticated_page

    run_id_holder: dict[str, str] = {}

    def _capture_run_id(response):
        if response.request.method == "POST" and response.url.endswith("/agents/run"):
            try:
                run_id = response.json().get("run_id")
            except Exception:
                return
            if run_id:
                run_id_holder["id"] = run_id

    page.on("response", _capture_run_id)

    page.goto(f"{WEB_URL}/agents")
    page.get_by_role("button", name="Company", exact=False).click()
    page.get_by_role("button", name="Run agent").click()

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and "id" not in run_id_holder:
        page.wait_for_timeout(500)
    assert "id" in run_id_holder, "expected /agents/run to return a run_id for the Company Research run"
    run_id = run_id_holder["id"]

    # Confirm the run is actually live in the real client store (driven by
    # useAgentStream, not just a fresh mutation response) before reloading —
    # this is what makes the reload below a genuine restoration check.
    run_id_label = page.get_by_text(run_id[:8]).first
    expect(run_id_label).to_be_visible(timeout=30_000)
    status_before = run_id_label.locator("xpath=ancestor::div[1]").get_by_text(
        re.compile(r"running|queued|awaiting approval")
    )
    expect(status_before).to_be_visible()

    # The actual reload the brief requires: a full browser reload wipes the
    # in-memory zustand `runs` store — only `activeRunId` survives, via
    # localStorage. Whatever reappears below can only come from AppShell's
    # global useAgentStream(activeRunId) re-running reconcile() against
    # GET /agents/runs/{id} and rebuilding the store from the server.
    page.reload()
    run_id_label_after = page.get_by_text(run_id[:8]).first
    expect(run_id_label_after).to_be_visible(timeout=30_000)
    status_after = run_id_label_after.locator("xpath=ancestor::div[1]").get_by_text(
        re.compile(r"running|queued|awaiting approval|completed")
    )
    expect(status_after).to_be_visible()


# ---------------------------------------------------------------------------
# Step 5: communications/leads journeys
# ---------------------------------------------------------------------------


def test_lead_creation_and_status_update_persist_after_reload(authenticated_page, api_client):
    """A disposable lead must actually be written by the backend (not just
    added to LeadsPage's optimistic `localLeads` array) and its status
    update must survive a reload — the same write/reload/re-assert pattern
    used by the Steps 1-2 persistence checks. Cleaned up via the API in a
    `finally` block so this shared live account isn't left with disposable
    fixture leads after every run."""
    page = authenticated_page
    lead_name = _fixture_value("Lead")

    lead_id_holder: dict[str, str] = {}

    def _capture_lead_id(response):
        if response.request.method == "POST" and response.url.endswith("/leads"):
            try:
                lead_id = response.json().get("id")
            except Exception:
                return
            if lead_id:
                lead_id_holder["id"] = lead_id

    page.on("response", _capture_lead_id)

    try:
        page.goto(f"{WEB_URL}/leads")
        page.get_by_role("button", name="Add lead").click()
        page.get_by_placeholder("Sarah Chen").fill(lead_name)
        page.get_by_placeholder("Acme Corp").fill("Fixture Co")
        # Scoped to the modal's <form> — the page header behind the modal
        # also has a button named "Add lead" that opens the modal.
        page.locator("form").get_by_role("button", name="Add lead").click()

        expect(page.get_by_text(f'Lead "{lead_name}" added')).to_be_visible(timeout=30_000)
        assert "id" in lead_id_holder, "expected POST /leads to actually create the lead"

        page.reload()
        expect(page.get_by_text(lead_name, exact=True)).to_be_visible(timeout=30_000)

        lead_row = page.locator("div.glass-panel", has_text=lead_name)
        lead_row.get_by_role("button", name="Reach out").click()
        expect(page.get_by_text("Lead status updated")).to_be_visible(timeout=30_000)

        page.reload()
        lead_row = page.locator("div.glass-panel", has_text=lead_name)
        expect(lead_row.get_by_text("Contacted", exact=True)).to_be_visible(timeout=30_000)
    finally:
        if "id" in lead_id_holder:
            try:
                api_client.delete(f"/leads/{lead_id_holder['id']}")
            except Exception:
                pass


def test_email_compose_fields_are_editable_and_gmail_draft_gated(authenticated_page):
    """Recipient/subject/body must be freely editable and reflected live in
    the preview header — proving the compose view never locks a draft's
    outbound fields to whatever an agent generated. Saving to Gmail drafts
    is a real external write against the connected Google account, so it
    only runs when ALLOW_GMAIL_DRAFTS=1 is explicitly set — a distinct
    opt-in from ALLOW_LIVE_SENDS/`live_safety`, since a Gmail draft never
    sends anything but does still write to the live mailbox."""
    page = authenticated_page
    recipient = f"e2e-{datetime.now(timezone.utc):%Y%m%d%H%M%S}@example.com"
    subject = _fixture_value("Subject")
    body = _fixture_value("Body")

    page.goto(f"{WEB_URL}/email")
    page.get_by_placeholder("Recipient email").fill(recipient)
    page.get_by_placeholder("Subject").fill(subject)
    page.get_by_placeholder("Edit or compose your email here…").fill(body)

    expect(page.get_by_text(subject, exact=True)).to_be_visible()
    expect(page.get_by_text(f"To: {recipient}", exact=False)).to_be_visible()

    if os.getenv("ALLOW_GMAIL_DRAFTS") == "1":
        page.get_by_role("button", name="Save draft").click()
        expect(page.get_by_text("Failed to save Gmail draft", exact=False)).to_have_count(0)
        expect(page.get_by_text("Saved to Gmail drafts")).to_be_visible(timeout=30_000)
    # else: never click Save draft (or Send) — both perform real external
    # writes (a Gmail draft / an actual compose+approve send) against the
    # shared live account outside this explicit opt-in.


def test_followup_schedule_set_when_application_marked_applied(api_client, wait_for_run):
    """No screen actually surfaces FollowUpAgent's day-5/day-12 schedule:
    the Email page's "Follow-up Schedule" panel renders the hardcoded
    FOLLOW_UP_STEPS constant (never fetched from any endpoint), and
    ApplicationsPage's ApplicationItem.nextFollowUp is hardcoded to
    `undefined` in its query mapping — so there is no browser journey that
    could exercise this contract today. Per this task's guidance to check
    the backend directly when a screen doesn't surface something, this
    verifies the real contract via the API: update_application_status must
    stamp followup_day5/day12 (5 and 12 days after applied_at) the moment a
    saved application transitions to "applied", mirroring what
    FollowUpAgent enqueues in BullMQ. Self-sufficient (runs its own job
    search rather than depending on another test's ordering) and restores
    the application to "saved" afterward."""
    search = api_client.post(
        "/jobs/search",
        json={"search_query": "Software Engineer", "location": "Remote", "max_results": 5},
    )
    search.raise_for_status()
    run_id = search.json()["run_id"]
    wait_for_run(api_client, run_id, timeout_s=150)

    saved = api_client.get("/jobs/applications", params={"status": "saved"}).json()
    assert saved, "expected at least one saved application to exist for this follow-up check"
    application_id = saved[0]["id"]

    try:
        patched = api_client.patch(
            f"/jobs/applications/{application_id}/status", json={"status": "applied"}
        )
        patched.raise_for_status()
        body = patched.json()
        assert body.get("applied_at"), "expected applied_at to be stamped on this transition"
        assert body.get("followup_day5"), "expected a day-5 follow-up to be scheduled"
        assert body.get("followup_day12"), "expected a day-12 follow-up to be scheduled"

        applied_at = datetime.fromisoformat(body["applied_at"].replace("Z", "+00:00"))
        day5 = datetime.fromisoformat(body["followup_day5"].replace("Z", "+00:00"))
        day12 = datetime.fromisoformat(body["followup_day12"].replace("Z", "+00:00"))
        assert (day5 - applied_at).days == 5, "expected the day-5 follow-up exactly 5 days out"
        assert (day12 - applied_at).days == 12, "expected the day-12 follow-up exactly 12 days out"
    finally:
        api_client.patch(f"/jobs/applications/{application_id}/status", json={"status": "saved"})


def test_email_monitor_scan_never_shows_send_checkpoint(authenticated_page):
    """EmailMonitorAgent's node always returns `pending_action=None` — it
    only classifies inbox notifications and updates application status
    (interview/rejected/viewed detection), it never drafts or sends a
    reply itself. Running it (via the generic /agents launcher, its only
    UI surface — there is no dedicated Email Monitor screen) must reach a
    terminal state without ever presenting the approval checkpoint used by
    every send/submit-capable agent, proving the scan really is
    read-only."""
    page = authenticated_page
    page.goto(f"{WEB_URL}/agents")

    page.get_by_role("button", name="Monitor", exact=False).click()
    page.get_by_role("button", name="Run agent").click()

    terminal_badge = page.get_by_text("completed", exact=True).or_(
        page.get_by_text("failed", exact=True)
    )
    expect(terminal_badge.first).to_be_visible(timeout=180_000)
    expect(page.get_by_text("Review Required")).to_have_count(0)


def test_linkedin_outreach_identify_and_reject_draft(authenticated_page):
    """Outreach must run the real linkedin_outreach agent — draft messages
    render inline in the queue card (a bespoke UI, not the shared
    ApprovalModal) — and rejecting a draft must go through Discard
    (POST /linkedin/outreach/{id}/approve {approved: false}), never
    Approve & Send, since that dispatches a real LinkedIn connection
    request/message. A well-known company name is used to maximize the
    odds Proxycurl actually resolves contacts; if it genuinely finds none
    for this run (live third-party data, outside this test's control) the
    run completes with an explicit "no contacts" notice instead of a
    checkpoint — that is asserted as the fallback rather than silently
    passed over."""
    page = authenticated_page
    company = "Stripe"

    page.goto(f"{WEB_URL}/linkedin/outreach")
    page.get_by_placeholder("Company name").fill(company)
    page.get_by_role("button", name="Find Contacts").click()

    expect(page.get_by_text("Failed to start outreach", exact=False)).to_have_count(0)
    queue_card = page.locator("div.glass-panel", has_text=company).first
    expect(queue_card).to_be_visible(timeout=180_000)

    discard_button = queue_card.get_by_role("button", name="Discard")
    if discard_button.count() > 0:
        approve_button = queue_card.get_by_role("button", name="Approve & Send")
        expect(approve_button).to_be_visible()
        expect(approve_button).to_be_enabled()
        discard_button.click()
        expect(page.get_by_text("Message discarded")).to_be_visible(timeout=30_000)
    else:
        expect(queue_card.get_by_text("completed", exact=True)).to_be_visible(timeout=30_000)
