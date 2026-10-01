"""
test_careercraft_full.py — Production-grade E2E test suite for CareerCraft AI.

Opens a REAL Chromium browser, navigates the actual running application,
and tests every feature: agents, browser automation, HITL gates, SSE streaming,
Gmail integration, and the full AutoApplyPipeline.

Requirements:
    - Full Docker Compose stack running: frontend, backend, temporal-worker, redis
    - pytest-playwright installed, Chromium browser installed
    - Environment variables: TEST_EMAIL, TEST_PASSWORD, TEST_JWT, WEB_URL, API_URL
      (ANTHROPIC_API_KEY optional — only for the settings key-save test)
    - Browser tests that need a signed-in user use conftest.py's
      `authenticated_page` (real Clerk sign-in), so they also need RUN_LIVE_E2E=1
    - Run: RUN_E2E=1 RUN_LIVE_E2E=1 pytest tests/e2e/test_careercraft_full.py -v -s

Safety: nothing here approves an email send or a job-application submission
unless ALLOW_LIVE_SENDS=1 (conftest.py's `live_safety`); otherwise HITL
checkpoints are asserted and then rejected.

Screenshots saved to: tests/e2e/screenshots/{test_name}/{step}.png
Videos saved to:      tests/e2e/videos/{test_name}.webm
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.getenv("WEB_URL") or os.getenv("BASE_URL", "http://localhost:3000")
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")
# /health is served at the app root (backend/app/main.py), not under /api/v1.
HEALTH_URL = f"{API_URL.removesuffix('/api/v1')}/health"
TEST_EMAIL = os.getenv("TEST_EMAIL", "")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "")
TEST_JWT = os.getenv("TEST_JWT", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
E2E_DIR = Path(__file__).resolve().parent
RESUME_FIXTURE = E2E_DIR.parent / "fixtures" / "test_resume.pdf"
SCREENSHOT_DIR = E2E_DIR / "screenshots"
VIDEO_DIR = E2E_DIR / "videos"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# Live agent runs routinely exceed pyproject.toml's global 60s pytest-timeout.
pytestmark = [pytest.mark.timeout(900)]

TERMINAL_RUN_STATUSES = {"completed", "awaiting_approval", "failed", "expired"}
_STATUS_TO_EVENT = {
    "completed": "complete",
    "awaiting_approval": "checkpoint",
    "failed": "error",
    "expired": "error",
}
# Throwaway recipient for drafts that are never sent.
DRAFT_RECIPIENT = "e2e-recruiter@example.com"


def ss(page: Page, test_name: str, step: str) -> None:
    path = SCREENSHOT_DIR / test_name
    path.mkdir(exist_ok=True)
    page.screenshot(path=str(path / f"{step}.png"), full_page=True)
    print(f"[SCREENSHOT] {test_name}/{step}.png")


def _error_message(payload) -> str:
    if isinstance(payload, dict):
        return str(payload.get("error") or payload.get("message") or payload)
    return str(payload)


def wait_for_sse_complete(client: httpx.Client, run_id: str, timeout_s: int = 120) -> dict:
    """Stream GET /agents/{run_id}/stream until the run's terminal event.

    Durable runs publish `checkpoint` with the run's pending_action (a dict
    whose "type" is the action type), `complete` with the result dict and
    `error` with {"error": ...} (app/workflows/agent_activities.py). Redis
    pub/sub does not replay events published before we subscribed, so every
    keep-alive `ping` also checks the persisted run (GET /agents/runs/{id}); a
    terminal state reached before the subscription is recovered from there.
    """
    checkpoint_seen = False
    events: list[dict] = []
    result: dict = {}
    event_type = "message"
    deadline = time.monotonic() + timeout_s
    with client.stream("GET", f"/agents/{run_id}/stream") as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if time.monotonic() > deadline:
                raise TimeoutError(f"Agent {run_id} timeout after {timeout_s}s")
            if line.startswith("event: "):
                event_type = line.split(":", 1)[1].strip()
                continue
            if not line.startswith("data: "):
                continue
            payload_str = line.split(":", 1)[1].strip()
            try:
                payload = json.loads(payload_str)
            except ValueError:
                payload = {"raw": payload_str}
            if event_type == "ping":
                run = client.get(f"/agents/runs/{run_id}").json()
                if run.get("status") not in TERMINAL_RUN_STATUSES:
                    continue
                event_type = _STATUS_TO_EVENT[run["status"]]
                payload = run.get("output") or {}
            events.append({"type": event_type, "payload": payload})
            print(f"  SSE [{event_type}]: {str(payload)[:120]}")
            if event_type == "complete":
                result = payload if isinstance(payload, dict) else {"value": payload}
                break
            if event_type == "checkpoint":
                checkpoint_seen = True
                result = {"checkpoint": payload, "run_id": run_id}
                break
            if event_type == "error":
                raise RuntimeError(f"Agent error: {_error_message(payload)}")
    return {"result": result, "events": events, "checkpoint_seen": checkpoint_seen}


def _start_run(client: httpx.Client, task_type: str, context: dict) -> str:
    """POST /agents/run — body is {task_type, context}; responds 200 {run_id, ...}."""
    r = client.post("/agents/run", json={"task_type": task_type, "context": context})
    assert r.status_code == 200, f"/agents/run {task_type} failed: {r.status_code} {r.text}"
    return r.json()["run_id"]


def _reject_if_awaiting(client: httpx.Client, run_id: str) -> None:
    """Best-effort cleanup: reject (never approve) a checkpoint this test left open."""
    try:
        run = client.get(f"/agents/runs/{run_id}").json()
        if run.get("status") == "awaiting_approval":
            client.post(f"/agents/{run_id}/approve", json={"approved": False})
    except Exception:
        pass


def _saved_application_id(client: httpx.Client, wait_for_run) -> str:
    """A saved JobApplication id. There is no create-application endpoint —
    rows come from job search — so run one (POST /jobs/search) if none exist."""
    saved = client.get("/jobs/applications", params={"status": "saved"}).json()
    if not saved:
        search = client.post(
            "/jobs/search",
            json={"search_query": "Software Engineer", "location": "Remote", "max_results": 5},
        )
        assert search.status_code == 200, f"/jobs/search failed: {search.text}"
        wait_for_run(client, search.json()["run_id"], 180)
        saved = client.get("/jobs/applications", params={"status": "saved"}).json()
    assert saved, "expected at least one saved application (job search persisted none)"
    return saved[0]["id"]


def _capture_run_id(page: Page, url_suffix: str) -> dict[str, str]:
    holder: dict[str, str] = {}

    def _on_response(response) -> None:
        if response.request.method == "POST" and response.url.endswith(url_suffix):
            try:
                run_id = response.json().get("run_id")
            except Exception:
                return
            if run_id:
                holder["id"] = run_id

    page.on("response", _on_response)
    return holder


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: Backend Health
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestBackendHealth:
    def test_health_endpoint(self, api_client: httpx.Client):
        r = httpx.get(HEALTH_URL, timeout=10)
        assert r.status_code == 200, f"/health failed: {r.text}"
        data = r.json()
        assert data["db"] == "ok", "Database not connected"
        assert data["redis"] == "ok", "Redis not connected"
        assert data["pgvector"] == "ok", "pgvector not enabled"
        # "degraded" = Temporal server or worker missing: agent runs cannot start.
        assert data["status"] == "ok", f"Backend degraded: temporal={data.get('temporal')}"
        print("BACKEND HEALTH: all systems ok")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: Authentication Flow
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestAuthentication:
    def test_login_page_loads(self, page: Page):
        page.goto(f"{BASE_URL}/login")
        expect(
            page.get_by_text("Sign in to continue", exact=False)
            .or_(page.get_by_role("heading", name="Dashboard"))
            .first
        ).to_be_visible(timeout=30000)
        ss(page, "auth", "01_login_page_loaded")
        print("AUTH: login page loaded")

    def test_email_magic_link_input(self, page: Page):
        page.goto(f"{BASE_URL}/login")
        email_input = page.locator("input[type='email']").first
        email_input.fill(TEST_EMAIL)
        ss(page, "auth", "02_email_entered")
        expect(page.locator("input[type='email']").first).to_have_value(TEST_EMAIL)
        print("AUTH: email accepts input")

    def test_dashboard_loads_after_auth(self, authenticated_page: Page):
        page = authenticated_page
        page.goto(f"{BASE_URL}/dashboard")
        expect(page).to_have_url(re.compile(r"/dashboard/?$"), timeout=30000)
        expect(page.get_by_role("heading", name="Dashboard")).to_be_visible(timeout=15000)
        ss(page, "auth", "03_dashboard_after_login")
        print("AUTH: dashboard loads after auth")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Settings — AI Model Configuration
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestSettings:
    def test_navigate_to_settings(self, authenticated_page: Page):
        page = authenticated_page
        page.goto(f"{BASE_URL}/settings")
        expect(page).to_have_url(re.compile(r"/settings/account/?$"), timeout=30000)
        ss(page, "settings", "01_settings_page")
        page.get_by_role("link", name="AI models & keys").first.click()
        expect(page).to_have_url(re.compile(r"/settings/models/?$"), timeout=30000)
        expect(page.get_by_role("heading", name="Model Settings")).to_be_visible()
        print("SETTINGS: page loads, AI models reachable")

    def test_api_key_save_and_mask(self, authenticated_page: Page):
        if not ANTHROPIC_API_KEY:
            pytest.skip("Set ANTHROPIC_API_KEY to save a real key through the UI")
        page = authenticated_page
        page.goto(f"{BASE_URL}/settings/models")
        ss(page, "settings", "02_ai_models_tab")
        page.locator("select[name='provider']").select_option("anthropic")
        api_key_input = page.get_by_placeholder("Paste provider API key")
        expect(api_key_input).to_have_attribute("type", "password")
        api_key_input.fill(ANTHROPIC_API_KEY)
        ss(page, "settings", "03_api_key_entered")
        page.get_by_role("button", name="Save API key").click()
        expect(page.get_by_text("Model added")).to_be_visible(timeout=30000)
        ss(page, "settings", "04_after_save")
        # Keys are never echoed back: the input clears and the model is listed.
        expect(page.get_by_placeholder("Paste provider API key")).to_have_value("")
        expect(page.get_by_text(ANTHROPIC_API_KEY)).to_have_count(0)
        expect(
            page.locator("[data-testid='model-row']").filter(has_text="anthropic").first
        ).to_be_visible(timeout=10000)
        print("SETTINGS: API key saved, listed as a model, never echoed")

    def test_settings_api_returns_masked_key(self, api_client: httpx.Client):
        r = api_client.get("/users/me/models")
        assert r.status_code == 200
        models = r.json()
        assert isinstance(models, list)
        for model in models:
            assert set(model) <= {"id", "provider", "model_name", "is_active"}, model
        if ANTHROPIC_API_KEY:
            assert ANTHROPIC_API_KEY not in r.text
        print("SETTINGS API: keys never returned (metadata only)")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: Document Upload → RAG Ingestion
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestRAGUpload:
    def test_upload_resume_via_ui(self, authenticated_page: Page):
        page = authenticated_page
        page.goto(f"{BASE_URL}/resume")
        page.wait_for_load_state("networkidle")
        ss(page, "rag", "01_resume_page")
        assert RESUME_FIXTURE.exists(), f"{RESUME_FIXTURE} missing"
        # The hidden file input uploads on selection (no separate submit).
        page.locator("input[type='file']").first.set_input_files(str(RESUME_FIXTURE))
        ss(page, "rag", "02_file_selected")
        expect(page.get_by_text("Upload failed", exact=False)).to_have_count(0)
        expect(page.get_by_text(f"Resume uploaded: {RESUME_FIXTURE.name}")).to_be_visible(
            timeout=60000
        )
        ss(page, "rag", "03_upload_success")
        print("RAG: resume uploaded and ingested")

    def test_rag_upload_api_directly(self, api_client: httpx.Client):
        with open(RESUME_FIXTURE, "rb") as f:
            r = httpx.post(
                f"{API_URL}/rag/upload",
                files={"file": ("test_resume.pdf", f, "application/pdf")},
                data={"doc_type": "resume"},
                headers={"Authorization": f"Bearer {TEST_JWT}"},
                timeout=120,
            )
        assert r.status_code == 201, f"RAG upload failed: {r.text}"
        data = r.json()
        assert data["doc_type"] == "resume"
        assert data["filename"].endswith("test_resume.pdf")
        assert data["embedded_at"], f"Uploaded but not indexed: {data.get('warning')}"
        docs = api_client.get("/rag/documents", params={"doc_type": "resume"}).json()
        assert data["id"] in [d["id"] for d in docs]
        print(f"RAG API: document {data['id']} indexed at {data['embedded_at']}")

    @pytest.mark.skip(
        reason="No equivalent endpoint: POST /rag/search was removed and no route "
        "exposes pgvector retrieval — RAGService.retrieve() is only called inside "
        "agents (/api/memory/* is agent memory, not document search)"
    )
    def test_rag_semantic_search(self, api_client: httpx.Client):
        pass


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: Job Search Agent
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestJobSearchAgent:
    def test_job_search_via_ui(self, authenticated_page: Page):
        page = authenticated_page
        page.goto(f"{BASE_URL}/jobs")
        page.wait_for_load_state("networkidle")
        ss(page, "job_search", "01_jobs_page")
        page.locator("input[name='query']").fill("Python Developer")
        page.locator("input[name='location']").fill("Bengaluru")
        ss(page, "job_search", "02_query_entered")
        page.get_by_role("button", name="Search — Run Job Agent").click()
        expect(page.get_by_text("Job Agent unavailable", exact=False)).to_have_count(0)
        expect(
            page.get_by_text("Job Agent started", exact=False)
            .or_(page.get_by_role("button", name="Searching — Job Agent running"))
            .first
        ).to_be_visible(timeout=30000)
        ss(page, "job_search", "03_results_loading")
        # The button returns to its idle label once the run finishes.
        expect(page.get_by_role("button", name="Search — Run Job Agent")).to_be_visible(
            timeout=180000
        )
        cards = page.locator("[data-testid='job-card']")
        expect(cards.first).to_be_visible(timeout=30000)
        ss(page, "job_search", "04_results_loaded")
        assert cards.count() > 0, "No job cards rendered"
        print(f"JOB SEARCH UI: {cards.count()} jobs rendered")

    def test_job_search_api_with_sse(self, api_client: httpx.Client):
        run_id = _start_run(
            api_client,
            "job_search",
            {"titles": ["Backend Developer"], "location": "Remote", "max_results": 5},
        )
        stream = wait_for_sse_complete(api_client, run_id, timeout_s=180)
        event_types = [e["type"] for e in stream["events"]]
        assert "thinking" in event_types, "No thinking events"
        assert "complete" in event_types, "No complete event"
        result = stream["result"]
        assert "matches" in result
        assert len(result["matches"]) > 0, f"No matches: {result.get('warnings')}"
        assert all(0 <= j["match_score"] <= 100 for j in result["matches"])
        print(f"JOB SEARCH SSE: {len(result['matches'])} jobs, {len(stream['events'])} events")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: Resume Agent
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestResumeAgent:
    def test_resume_optimization_via_ui(self, authenticated_page: Page):
        page = authenticated_page
        page.goto(f"{BASE_URL}/resume")
        page.wait_for_load_state("networkidle")
        ss(page, "resume", "01_resume_page")
        page.get_by_placeholder("Paste the job description here… CareerCraft AI", exact=False).fill(
            "Senior Python Engineer with 5+ years experience. "
            "Skills: Python, FastAPI, PostgreSQL, Docker, Redis, LangChain."
        )
        ss(page, "resume", "02_jd_entered")
        page.get_by_role("button", name="Tailor Resume").click()
        expect(page.get_by_text("Tailored ATS score:", exact=False)).to_be_visible(timeout=180000)
        ss(page, "resume", "03_ats_score_shown")
        expect(page.get_by_role("button", name="Export")).to_be_enabled(timeout=30000)
        ss(page, "resume", "04_download_available")
        print("RESUME: ATS score displayed, download available")

    def test_resume_api_returns_ats_score(self, api_client: httpx.Client):
        r = api_client.post(
            "/resume/optimize",
            json={"jd_text": "Senior Python Engineer FastAPI PostgreSQL", "template": "modern"},
            timeout=180,
        )
        assert r.status_code == 200, f"Optimize failed: {r.text}"
        data = r.json()
        assert data["status"] == "awaiting_approval"
        assert 0 <= data["ats_score"] <= 100
        assert len(data["resume_markdown"]) > 100
        assert isinstance(data["keywords_matched"], list)
        assert isinstance(data["keywords_missing"], list)
        assert data["pdf_available"] and data["pdf_document_id"]
        print(f"RESUME API: ATS={data['ats_score']}, {len(data['keywords_missing'])} missing kw")

    def test_resume_pdf_download(self, api_client: httpx.Client):
        r = api_client.post(
            "/resume/optimize",
            json={"jd_text": "Python Backend Engineer REST APIs", "template": "modern"},
            timeout=180,
        )
        assert r.status_code == 200, f"Optimize failed: {r.text}"
        doc_id = r.json()["pdf_document_id"]
        assert doc_id, "No PDF was stored for the tailored resume"
        r2 = api_client.get(f"/resume/download/{doc_id}")
        assert r2.status_code == 200
        assert r2.headers["content-type"] == "application/pdf"
        assert len(r2.content) > 1000
        out_dir = E2E_DIR / "outputs"
        out_dir.mkdir(exist_ok=True)
        (out_dir / f"resume_{doc_id}.pdf").write_bytes(r2.content)
        print(f"RESUME PDF: {len(r2.content)} bytes downloaded")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 7: Cover Letter Agent
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestCoverLetterAgent:
    def test_cover_letter_via_ui(self, authenticated_page: Page):
        page = authenticated_page
        page.goto(f"{BASE_URL}/cover-letter")
        page.wait_for_load_state("networkidle")
        ss(page, "cover_letter", "01_page_loaded")
        page.locator("textarea[name='job_description']").fill(
            "Senior Python Engineer at Zepto. FastAPI, distributed systems, 5+ years."
        )
        # Tone options are a radiogroup (Segmented asTabs={false} → role="radio").
        professional = page.get_by_role("radio", name="Professional")
        professional.click()
        expect(professional).to_have_attribute("aria-checked", "true")
        ss(page, "cover_letter", "02_form_filled")
        page.get_by_role("button", name="Generate Cover Letter").click()
        letter = page.locator("#cover-letter-body")
        expect(letter).to_be_visible(timeout=180000)
        assert letter.input_value().strip(), "Generated cover letter is empty"
        ss(page, "cover_letter", "03_letter_generated")
        expect(page.get_by_role("group", name="Draft versions")).to_be_visible()
        ss(page, "cover_letter", "04_variants_visible")
        print("COVER LETTER: generated with variants")

    def test_cover_letter_api(self, api_client: httpx.Client):
        r = api_client.post(
            "/cover-letter/generate",
            json={
                "jd_text": "Python Backend Engineer at Swiggy, Bangalore. FastAPI, Kafka.",
                "tone": "formal",
            },
            timeout=180,
        )
        assert r.status_code == 200, f"CL failed: {r.text}"
        data = r.json()
        assert data["status"] == "awaiting_approval", data
        assert data["tone"] == "formal"
        assert data["content"] and len(data["content"]) > 200
        assert isinstance(data["warnings"], list)
        print(f"COVER LETTER API: {len(data['content'].split())} words, run {data['run_id']}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 8: LinkedIn Agent
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestLinkedInAgent:
    def test_linkedin_optimize_api(self, api_client: httpx.Client, wait_for_run):
        # No /linkedin/optimize route — profile optimization is the
        # linkedin_optimize agent task (orchestrator → linkedin_agent_node).
        run_id = _start_run(
            api_client, "linkedin_optimize", {"target_role": "Senior Software Engineer"}
        )
        try:
            run = wait_for_run(api_client, run_id, 180)
            assert run["status"] == "awaiting_approval", run
            data = run["output"]
            assert data["type"] == "linkedin_edits"
            assert 0 < len(data["headline"]) <= 220
            assert len(data["about"]) > 100
            assert isinstance(data["experience_bullets"], str)
            print(f"LINKEDIN API: headline='{data['headline'][:50]}...'")
        finally:
            _reject_if_awaiting(api_client, run_id)

    def test_linkedin_via_ui(self, authenticated_page: Page):
        page = authenticated_page
        page.goto(f"{BASE_URL}/linkedin")
        page.wait_for_load_state("networkidle")
        ss(page, "linkedin", "01_page_loaded")
        page.get_by_placeholder("e.g. Senior Python Engineer").fill("Software Engineer")
        ss(page, "linkedin", "02_form_filled")
        page.get_by_role("button", name="Run Analysis").first.click()
        expect(page.get_by_text("Agent unavailable", exact=False)).to_have_count(0)
        # The run stops at the HITL checkpoint (approval modal) with drafts
        # rendered behind it; never approve — publishing is a one-way action.
        expect(
            page.get_by_role("dialog", name="Review Required")
            .or_(page.locator("[data-testid='linkedin-headline']"))
            .first
        ).to_be_visible(timeout=180000)
        ss(page, "linkedin", "03_results_shown")
        print("LINKEDIN UI: optimization results displayed")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 9: Company Research Agent
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestCompanyResearchAgent:
    def test_company_research_api(self, api_client: httpx.Client, wait_for_run):
        run_id = _start_run(api_client, "company_research", {"company_name": "Infosys"})
        run = wait_for_run(api_client, run_id, timeout_s=180)
        assert run["status"] == "completed", run
        data = run["output"]
        assert data["company_name"] == "Infosys"
        assert len(data.get("culture_summary") or data.get("overview") or "") > 50
        intel = api_client.get("/company/Infosys/intel")
        assert intel.status_code == 200, intel.text
        assert intel.json()["company_name"] == "Infosys"
        assert "id" in intel.json()
        print(f"COMPANY RESEARCH: Infosys — {len(str(data))} bytes")

    def test_company_research_caching(self, api_client: httpx.Client, wait_for_run):
        context = {"company_name": "Infosys"}
        t1 = time.time()
        first = wait_for_run(api_client, _start_run(api_client, "company_research", context), 180)
        t1_end = time.time()
        t2 = time.time()
        second = wait_for_run(api_client, _start_run(api_client, "company_research", context), 180)
        t2_end = time.time()
        assert first["status"] == "completed" and second["status"] == "completed"
        # company_research_node returns the stored brief (7-day TTL) with cached=True.
        assert second["output"].get("cached") is True, "Caching not working"
        print(f"CACHING: 1st={t1_end - t1:.2f}s, 2nd={t2_end - t2:.2f}s")

    def test_company_research_via_ui(self, authenticated_page: Page):
        page = authenticated_page
        page.goto(f"{BASE_URL}/company")
        page.wait_for_load_state("networkidle")
        ss(page, "company", "01_page_loaded")
        page.locator("input[name='company']").fill("Zepto")
        page.get_by_role("button", name="Research").click()
        expect(page.get_by_text("Research failed", exact=False)).to_have_count(0)
        expect(page.get_by_text("Overview")).to_be_visible(timeout=180000)
        expect(page.get_by_text("Culture")).to_be_visible()
        ss(page, "company", "02_research_results")
        print("COMPANY UI: Zepto intelligence report displayed")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 10: Salary Agent
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestSalaryAgent:
    def test_salary_benchmark_api(self, api_client: httpx.Client, wait_for_run):
        run_id = _start_run(
            api_client,
            "salary_intelligence",
            {
                "role": "Senior Software Engineer",
                "location": "Bengaluru, India",
                "offer_amount": 1800000,
            },
        )
        try:
            run = wait_for_run(api_client, run_id, timeout_s=180)
            assert run["status"] in {"awaiting_approval", "completed"}, run
            output = run["output"] or {}
            data = output.get("report") or output
            if data.get("data_unavailable"):
                pytest.skip(f"No published salary figures found ({data.get('data_sources')})")
            assert 0 < data["p25"] <= data["p50"] <= data["p75"]
            assert output.get("script"), "No negotiation script"
            print(f"SALARY API: p50={data['p50']}")
        finally:
            _reject_if_awaiting(api_client, run_id)

    def test_salary_via_ui(self, authenticated_page: Page):
        page = authenticated_page
        page.goto(f"{BASE_URL}/salary")
        page.wait_for_load_state("networkidle")
        ss(page, "salary", "01_page_loaded")
        page.locator("input[name='role']").fill("Senior Software Engineer")
        page.locator("input[name='location']").fill("Bengaluru")
        page.locator("input[name='experience_years']").fill("4")
        ss(page, "salary", "02_form_filled")
        page.get_by_role("button", name="Benchmark & Generate Report").click()
        expect(
            page.get_by_text("Market Percentiles")
            .or_(page.get_by_text("Not enough published salary figures", exact=False))
            .first
        ).to_be_visible(timeout=180000)
        ss(page, "salary", "03_results")
        print("SALARY UI: percentiles and negotiation script displayed")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 11: Interview Coach Agent
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestInterviewCoachAgent:
    def test_interview_session_full_flow(self, api_client: httpx.Client):
        r = api_client.post(
            "/interview/session/start",
            json={"role": "SDE-2", "company": "Amazon", "question_type": "behavioral"},
            timeout=180,
        )
        assert r.status_code == 200, f"Session start failed: {r.text}"
        data = r.json()
        session_id = data["session_id"]
        first_q = data["question"]["question"]
        assert data["question_index"] == 0
        assert len(first_q) > 10
        print(f"  Q1: {first_q[:80]}...")

        r2 = api_client.post(
            f"/interview/session/{session_id}/answer",
            json={
                "question_index": 0,
                "answer_text": (
                    "In my previous role at a fintech, I delivered a payment gateway "
                    "under a 2-week deadline by breaking it into auth, processing, and "
                    "error handling. Delivered on time, reduced failures by 30%."
                ),
            },
            timeout=180,
        )
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        assert 0 <= d2["feedback"]["score"] <= 100
        assert d2["feedback"]["tips"], "No feedback tips"
        # Sessions have >= 5 questions, so the first answer never completes it.
        assert d2["next_question"] is not None and d2["summary"] is None
        print(f"  Score: {d2['feedback']['score']}/100 ({d2['feedback']['rating']})")
        print(f"  Q2: {d2['next_question']['question'][:80]}...")

        r3 = api_client.post(
            f"/interview/session/{session_id}/answer",
            json={
                "question_index": 1,
                "answer_text": (
                    "I disagreed with my tech lead on DB design. I prepared a "
                    "data-driven comparison with benchmarks. After structured discussion "
                    "we combined ideas, achieving 40% better query performance."
                ),
            },
            timeout=180,
        )
        assert r3.status_code == 200, r3.text
        summary = api_client.get(f"/interview/session/{session_id}/summary")
        assert summary.status_code == 200
        assert len(summary.json()["scores"]) == 2
        print("INTERVIEW: 2 answers scored, session summary returned")

    def test_interview_via_ui(self, authenticated_page: Page):
        page = authenticated_page
        page.goto(f"{BASE_URL}/interview?tab=coach")
        page.wait_for_load_state("networkidle")
        ss(page, "interview", "01_page_loaded")
        page.get_by_placeholder("Target Role *").fill("Software Engineer")
        page.get_by_placeholder("Company (optional)").fill("Google")
        page.get_by_role("radio", name="Behavioral").click()
        ss(page, "interview", "02_form_filled")
        page.get_by_role("button", name="Start Session").click()
        expect(page.get_by_text("Failed to start session")).to_have_count(0)
        expect(page.locator("[data-testid='interview-question']")).to_be_visible(timeout=180000)
        ss(page, "interview", "03_first_question")
        page.get_by_placeholder("Type your answer (minimum 10 words)...").fill(
            "I coordinated 3 microservices for a distributed system, implemented "
            "circuit breakers, and achieved 99.9% uptime."
        )
        ss(page, "interview", "04_answer_typed")
        page.get_by_role("button", name="Submit Answer").click()
        expect(page.get_by_text("Previous Feedback")).to_be_visible(timeout=180000)
        expect(page.get_by_text("Q1:", exact=False)).to_be_visible()
        ss(page, "interview", "05_score_shown")
        print("INTERVIEW UI: question, answer, scores shown")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 12: Email Agent + HITL Gate
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.security
class TestEmailAgentHITL:
    def test_email_compose_api_no_send(self, api_client: httpx.Client):
        r = api_client.post(
            "/email/compose",
            json={
                "company": "Flipkart",
                "role": "Senior Engineer",
                "recipient_email": DRAFT_RECIPIENT,
            },
            timeout=180,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "awaiting_approval"
        draft = data["draft"]
        assert draft["type"] == "send_email"
        assert len(draft["body"]) > 50
        assert draft["recipient"] == DRAFT_RECIPIENT
        print("EMAIL HITL: draft created, awaiting_approval — NOT sent")

    def test_email_hitl_gate_via_agent_run(self, api_client: httpx.Client):
        run_id = _start_run(
            api_client,
            "email",
            {"company": "Razorpay", "role": "Backend Engineer", "recipient_email": DRAFT_RECIPIENT},
        )
        try:
            stream = wait_for_sse_complete(api_client, run_id, timeout_s=180)
            assert stream["checkpoint_seen"], "HITL checkpoint never fired"
            cp = stream["result"]["checkpoint"]
            assert cp["type"] == "send_email"
            assert cp["recipient"] == DRAFT_RECIPIENT
            assert cp["body"]
            print(f"EMAIL HITL checkpoint: to={cp['recipient']}, awaiting approval")
        finally:
            _reject_if_awaiting(api_client, run_id)

    def test_approve_email_sends_it(self, api_client: httpx.Client, wait_for_run, live_safety):
        if not live_safety.allow_external_writes:
            pytest.skip("Real email send — set ALLOW_LIVE_SENDS=1 to approve it")
        run_id = _start_run(
            api_client,
            "email",
            {"company": "Test Corp", "role": "Engineer", "recipient_email": TEST_EMAIL},
        )
        run = wait_for_run(api_client, run_id, 180)
        assert run["status"] == "awaiting_approval", run
        r2 = api_client.post(f"/agents/{run_id}/approve", json={"approved": True})
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "queued"
        final = wait_for_run(api_client, run_id, 120)
        assert final["status"] == "completed", final
        assert final["output"].get("sent") is True
        print("EMAIL HITL approve: email sent after approval")

    def test_cancel_email_prevents_send(self, api_client: httpx.Client, wait_for_run):
        run_id = _start_run(
            api_client,
            "email",
            {"company": "Test Inc", "role": "Engineer", "recipient_email": DRAFT_RECIPIENT},
        )
        run = wait_for_run(api_client, run_id, 180)
        assert run["status"] == "awaiting_approval", run
        r2 = api_client.post(f"/agents/{run_id}/approve", json={"approved": False})
        assert r2.status_code == 200
        assert r2.json()["status"] == "cancelled"
        r3 = api_client.get(f"/agents/runs/{run_id}").json()
        # A rejected run is closed as failed with the cancellation recorded.
        assert r3["status"] == "failed"
        assert r3["error"] == "Action cancelled by user"
        print("EMAIL HITL cancel: run cancelled, email NOT sent")

    def test_wrong_user_cannot_approve(self, api_client: httpx.Client, wait_for_run):
        run_id = _start_run(
            api_client,
            "email",
            {"company": "Y", "role": "Z", "recipient_email": DRAFT_RECIPIENT},
        )
        try:
            r2 = httpx.post(
                f"{API_URL}/agents/{run_id}/approve",
                json={"approved": True},
                headers={
                    "Authorization": "Bearer fake.jwt.token",
                    "Content-Type": "application/json",
                },
            )
            assert r2.status_code in (401, 403), f"Wrong user not blocked: {r2.status_code}"
            print("SECURITY: wrong JWT blocked from approval")
        finally:
            wait_for_run(api_client, run_id, 180)
            _reject_if_awaiting(api_client, run_id)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 13: Follow-Up Agent
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestFollowUpAgent:
    def test_followup_schedule_enqueues_jobs(self, api_client: httpx.Client, wait_for_run):
        # follow_up is not an agent task_type: marking an application "applied"
        # stamps followup_day5/day12 and starts its FollowupWorkflow, which later
        # drafts (never sends) each follow-up for approval.
        app_id = _saved_application_id(api_client, wait_for_run)
        try:
            r = api_client.patch(f"/jobs/applications/{app_id}/status", json={"status": "applied"})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["applied_at"], "applied_at not stamped"
            assert body["followup_day5"] and body["followup_day12"], "Follow-ups not scheduled"
            print(f"FOLLOW-UP: day-5 {body['followup_day5']}, day-12 {body['followup_day12']}")
        finally:
            api_client.patch(f"/jobs/applications/{app_id}/status", json={"status": "saved"})


# ══════════════════════════════════════════════════════════════════════════════
# TEST 14: Natural Language Search Agent
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestNLSearchAgent:
    def test_nl_search_parses_and_executes(self, api_client: httpx.Client, wait_for_run):
        run_id = _start_run(
            api_client,
            "nl_job_search",
            {"query": "senior backend engineer remote India paying above 20 lakhs"},
        )
        run = wait_for_run(api_client, run_id, 180)
        # Step 1: the parsed interpretation is gated for confirmation.
        assert run["status"] == "awaiting_approval", run
        pending = run["output"]
        assert pending["type"] == "search_confirmation"
        parsed = pending["interpretation"]
        assert parsed["role_title"], parsed
        assert "location" in parsed
        # Step 2: confirming only runs a read-only job search (no send/submit).
        r = api_client.post(f"/agents/{run_id}/approve", json={"approved": True})
        assert r.status_code == 200, r.text
        final = wait_for_run(api_client, run_id, 180)
        assert final["status"] == "completed", final
        result = final["output"]
        assert "matches" in result
        print(
            f"NL SEARCH: '{parsed['role_title']}' in {parsed.get('location') or '?'}, "
            f"{len(result['matches'])} jobs"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TEST 15: AutoApply Pipeline — THE FULL FLOW
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.security
class TestAutoApplyPipeline:
    def test_auto_apply_two_hitl_gates(self, api_client: httpx.Client, wait_for_run, live_safety):
        # Gate 1 is the pipeline's batch approval (auto_apply_approval). Gate 2
        # is per application: each approved apply_browser action starts its own
        # AutoApplyWorkflow that still waits for a final submit review.
        run_id = _start_run(
            api_client,
            "auto_apply",
            {"search_query": "Python Developer", "location": "Remote", "max_applications": 1},
        )
        print(f"  Run ID: {run_id}")
        run = wait_for_run(api_client, run_id, 300)
        assert run["status"] in {"awaiting_approval", "completed"}, run
        output = run["output"]
        if run["status"] == "completed":
            # auto_mode "drafts": drafts are saved for review and nothing is queued.
            assert "applications" in output, output
            print(f"AUTOAPPLY: drafts mode — {len(output['applications'])} drafts, no gate")
            return

        assert output["type"] == "auto_apply_approval"
        actions = output["actions_pending"]
        assert actions, "Gate 1 has no pending actions"
        for action in actions:
            assert action["action"] in {"apply_browser", "send_email"}, action
            if action["action"] == "apply_browser":
                assert action["job_url"] and action["pdf_document_id"]
                assert action["resume_markdown"]
            else:
                assert action["to"] and action["body"]
        print(f"  GATE 1: {len(actions)} actions pending review")

        if not live_safety.allow_external_writes:
            r = api_client.post(f"/agents/{run_id}/approve", json={"approved": False})
            assert r.status_code == 200 and r.json()["status"] == "cancelled"
            final = api_client.get(f"/agents/runs/{run_id}").json()
            assert final["error"] == "Action cancelled by user"
            print("AUTOAPPLY: gate 1 rejected (set ALLOW_LIVE_SENDS=1 to approve)")
            return

        r = api_client.post(f"/agents/{run_id}/approve", json={"approved": True})
        assert r.status_code == 200, r.text
        final = wait_for_run(api_client, run_id, 120)
        assert final["status"] == "completed", final
        result = final["output"]
        assert "application_workflows" in result and "child_run_ids" in result
        print(
            f"AUTOAPPLY: gate 1 approved — {len(result['application_workflows'])} application "
            "workflows awaiting their final submit review"
        )

    def test_auto_apply_ui_flow(
        self, authenticated_page: Page, api_client: httpx.Client, wait_for_run, live_safety
    ):
        # The generic /agents launcher is the only UI surface for auto_apply.
        page = authenticated_page
        run_id_holder = _capture_run_id(page, "/agents/run")
        page.goto(f"{BASE_URL}/agents")
        page.wait_for_load_state("networkidle")
        ss(page, "auto_apply", "01_agents_page")
        page.get_by_role("button", name="Auto Apply", exact=False).click()
        page.get_by_role("button", name="Run agent").click()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and "id" not in run_id_holder:
            page.wait_for_timeout(500)
        assert "id" in run_id_holder, "expected /agents/run to return a run_id"
        run_id = run_id_holder["id"]
        ss(page, "auto_apply", "03_agent_running")

        run = wait_for_run(api_client, run_id, 300)
        assert run["status"] in {"awaiting_approval", "completed"}, run
        if run["status"] == "completed":
            expect(page.get_by_role("dialog", name="Review Required")).to_have_count(0)
            print("AUTOAPPLY UI: drafts mode — completed without an approval gate")
            return

        dialog = page.get_by_role("dialog", name="Review Required")
        expect(dialog).to_be_visible(timeout=60000)
        ss(page, "auto_apply", "04_hitl_gate_1_modal")
        approve = dialog.get_by_role("button", name="Approve & Execute")
        expect(approve).to_be_enabled()
        if live_safety.allow_external_writes:
            approve.click()
            expect(page.get_by_text("Action approved")).to_be_visible(timeout=30000)
            ss(page, "auto_apply", "05_gate_1_approved")
            print("AUTOAPPLY UI: gate 1 approved; each application awaits final review")
        else:
            dialog.get_by_role("button", name="Cancel").click()
            final = wait_for_run(api_client, run_id, 30)
            assert final["status"] == "failed" and final["error"] == "Action cancelled by user"
            ss(page, "auto_apply", "05_gate_1_rejected")
            print("AUTOAPPLY UI: gate 1 rejected (set ALLOW_LIVE_SENDS=1 to approve)")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 16: Applications Kanban
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestApplicationsKanban:
    def test_applications_list(self, api_client: httpx.Client):
        r = api_client.get("/jobs/applications")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        for app in data:
            assert {"id", "company", "role", "status"} <= set(app)
        print(f"APPLICATIONS: {len(data)} total")

    def test_application_status_update(self, api_client: httpx.Client, wait_for_run):
        app_id = _saved_application_id(api_client, wait_for_run)
        try:
            r2 = api_client.patch(
                f"/jobs/applications/{app_id}/status", json={"status": "interview"}
            )
            assert r2.status_code == 200, r2.text
            assert r2.json()["status"] == "interview"
            print("APPLICATIONS: status updated 'saved' → 'interview'")
        finally:
            api_client.patch(f"/jobs/applications/{app_id}/status", json={"status": "saved"})

    def test_kanban_drag_via_ui(self, authenticated_page: Page, api_client: httpx.Client):
        page = authenticated_page
        page.goto(f"{BASE_URL}/applications")
        page.wait_for_load_state("networkidle")
        ss(page, "kanban", "01_kanban_loaded")
        if not api_client.get("/jobs/applications").json():
            # The board only renders once there is at least one application.
            expect(page.get_by_text("Your tracker is ready")).to_be_visible(timeout=30000)
            print("KANBAN: empty tracker state shown (no applications yet)")
            return
        columns = page.locator("[data-column-status]")
        expect(columns.first).to_be_visible(timeout=30000)
        assert columns.count() >= 4, f"Expected 4+ kanban columns, got {columns.count()}"
        ss(page, "kanban", "02_columns_visible")
        print(f"KANBAN: {columns.count()} columns visible")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 17: SSE Infrastructure
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
class TestSSEInfrastructure:
    def test_sse_stream_content_type(self, api_client: httpx.Client, wait_for_run):
        bad = api_client.get("/agents/not-a-uuid/stream")
        assert bad.status_code == 400
        # email_monitor is a read-only inbox scan — a cheap run to stream.
        run_id = _start_run(api_client, "email_monitor", {})
        with api_client.stream("GET", f"/agents/{run_id}/stream") as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers.get("content-type", "")
        wait_for_run(api_client, run_id, 120)
        print("SSE: content-type verified")

    def test_sse_events_in_correct_order(self, api_client: httpx.Client):
        run_id = _start_run(api_client, "resume_optimize", {"jd_text": "Python FastAPI Engineer"})
        try:
            stream = wait_for_sse_complete(api_client, run_id, timeout_s=180)
            types = [e["type"] for e in stream["events"]]
            assert "thinking" in types
            # Resume drafts end at a resume_ready checkpoint; others end at complete.
            assert types[-1] in {"complete", "checkpoint"}, f"Last event is {types[-1]}"
            assert types.index(types[-1]) == len(types) - 1, "Events after the terminal one"
            assert types.index("thinking") < len(types) - 1
            unique_order = list(dict.fromkeys(types))
            print(f"SSE ORDER: {' → '.join(unique_order)} ({len(types)} events)")
        finally:
            _reject_if_awaiting(api_client, run_id)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 18: Security Verification
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.security
class TestSecurityVerification:
    def test_all_protected_endpoints_require_jwt(self):
        endpoints = [
            ("GET", "/users/me"),
            ("POST", "/agents/run"),
            ("GET", "/jobs/applications"),
            ("POST", "/rag/upload"),
            ("POST", "/resume/optimize"),
            ("GET", "/leads"),
            ("POST", "/cover-letter/generate"),
            ("POST", "/interview/session/start"),
        ]
        for method, path in endpoints:
            r = httpx.request(method, f"{API_URL}{path}", timeout=10)
            assert (
                r.status_code == 401
            ), f"{method} {path} returned {r.status_code} without JWT (expected 401)"
        print(f"SECURITY: all {len(endpoints)} endpoints require JWT")

    def test_internal_routes_return_404_publicly(self):
        r = httpx.get("http://localhost/internal/agents/followup", timeout=5)
        assert r.status_code == 404, f"/internal/ not blocked: {r.status_code}"
        print("SECURITY: /internal/ routes blocked (Nginx)")

    def test_rate_limiting_fires(self, api_client: httpx.Client):
        # Only decorated routes are limited (no global default); GET /leads is
        # a cheap read-only route limited to 30/minute per user.
        statuses: list[int] = []
        for _ in range(35):
            r = api_client.get("/leads")
            statuses.append(r.status_code)
            if r.status_code == 429:
                break
        assert 429 in statuses, "Rate limit never triggered"
        print("SECURITY: 429 returned after rate limit exceeded")


# ══════════════════════════════════════════════════════════════════════════════
# Terminal Summary
# ══════════════════════════════════════════════════════════════════════════════


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    print("\n" + "=" * 70)
    print("CareerCraft AI — End-to-End Test Results")
    print("=" * 70)
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    skipped = len(terminalreporter.stats.get("skipped", []))
    print(f"  PASSED:  {passed}")
    print(f"  FAILED:  {failed}")
    print(f"  SKIPPED: {skipped}")
    print("  Screenshots: tests/e2e/screenshots/")
    print("  Videos:      tests/e2e/videos/")
    print("=" * 70)
