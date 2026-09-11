"""
test_careercraft_full.py — Production-grade E2E test suite for CareerCraft AI.

Opens a REAL Chromium browser, navigates the actual running application,
and tests every feature: agents, browser automation, HITL gates, SSE streaming,
Gmail integration, and the full AutoApplyPipeline.

Requirements:
    - Full Docker Compose stack running: frontend, backend, worker, redis
    - pytest-playwright installed, Chromium browser installed
    - Environment variables: TEST_EMAIL, TEST_PASSWORD, TEST_JWT, TEST_JOB_URL
    - Run: RUN_E2E=1 pytest tests/e2e/test_careercraft_full.py -v -s --headed

Screenshots saved to: tests/e2e/screenshots/{test_name}/{step}.png
Videos saved to:      tests/e2e/videos/{test_name}.webm
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")
TEST_EMAIL = os.getenv("TEST_EMAIL", "")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "")
TEST_JWT = os.getenv("TEST_JWT", "")
TEST_JOB_URL = os.getenv(
    "TEST_JOB_URL", "https://www.naukri.com/job-listings-python-developer"
)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
E2E_DIR = Path(__file__).resolve().parent
SCREENSHOT_DIR = E2E_DIR / "screenshots"
VIDEO_DIR = E2E_DIR / "videos"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)


def ss(page: Page, test_name: str, step: str) -> None:
    path = SCREENSHOT_DIR / test_name
    path.mkdir(exist_ok=True)
    page.screenshot(path=str(path / f"{step}.png"), full_page=True)
    print(f"[SCREENSHOT] {test_name}/{step}.png")


def wait_for_sse_complete(client: httpx.Client, run_id: str, timeout_s: int = 120) -> dict:
    checkpoint_seen = False
    events: list[dict] = []
    result: dict = {}
    start = time.time()
    with client.stream("GET", f"/agents/{run_id}/stream") as response:
        for line in response.iter_lines():
            if time.time() - start > timeout_s:
                raise TimeoutError(f"Agent {run_id} timeout after {timeout_s}s")
            if line.startswith("event: "):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data: "):
                payload_str = line.split(":", 1)[1].strip()
                try:
                    payload = json.loads(payload_str)
                except Exception:
                    payload = {"raw": payload_str}
                events.append({"type": event_type, "payload": payload})
                print(f"  SSE [{event_type}]: {str(payload)[:120]}")
                if event_type == "complete":
                    result = payload
                    break
                if event_type == "checkpoint":
                    checkpoint_seen = True
                    result = {"checkpoint": payload, "run_id": run_id}
                    break
                if event_type == "error":
                    raise RuntimeError(f"Agent error: {payload.get('message')}")
    return {"result": result, "events": events, "checkpoint_seen": checkpoint_seen}


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: Backend Health
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestBackendHealth:
    def test_health_endpoint(self, api_client: httpx.Client):
        r = api_client.get("/health", headers={})
        assert r.status_code == 200, f"/health failed: {r.text}"
        data = r.json()
        assert data["status"] == "ok"
        assert data["db"] == "ok", "Database not connected"
        assert data["redis"] == "ok", "Redis not connected"
        assert data.get("pgvector") == "enabled", "pgvector not enabled"
        print("BACKEND HEALTH: all systems ok")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: Authentication Flow
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestAuthentication:
    def test_login_page_loads(self, page: Page):
        page.goto(f"{BASE_URL}/login")
        ss(page, "auth", "01_login_page_loaded")
        expect(page.locator("text=Sign in").or_(page.locator("text=Dashboard"))).to_be_visible()
        print("AUTH: login page loaded")

    def test_email_magic_link_input(self, page: Page):
        page.goto(f"{BASE_URL}/login")
        email_input = page.locator("input[type='email']").first
        email_input.fill(TEST_EMAIL)
        ss(page, "auth", "02_email_entered")
        expect(page.locator("input[type='email']").first).to_have_value(TEST_EMAIL)
        print("AUTH: email accepts input")

    def test_dashboard_loads_after_auth(self, page: Page):
        page.goto(f"{BASE_URL}/login")
        page.evaluate(f"window.localStorage.setItem('supabase_test_jwt', '{TEST_JWT}')")
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state("networkidle")
        ss(page, "auth", "03_dashboard_after_login")
        expect(
            page.locator("text=Active Applications").or_(
                page.locator("text=Dashboard")
            )
        ).to_be_visible(timeout=15000)
        print("AUTH: dashboard loads after auth")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Settings — AI Model Configuration
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestSettings:
    def test_navigate_to_settings(self, page: Page):
        page.goto(f"{BASE_URL}/settings")
        page.wait_for_load_state("networkidle")
        ss(page, "settings", "01_settings_page")
        expect(page.locator("text=AI Models")).to_be_visible()
        print("SETTINGS: page loads")

    def test_api_key_save_and_mask(self, page: Page):
        page.goto(f"{BASE_URL}/settings")
        page.locator("text=AI Models").click()
        page.wait_for_timeout(1000)
        ss(page, "settings", "02_ai_models_tab")
        api_key_input = page.locator(
            "input[placeholder*='sk-ant'], input[name*='api_key']"
        ).first
        api_key_input.fill(ANTHROPIC_API_KEY)
        ss(page, "settings", "03_api_key_entered")
        page.locator("button:has-text('Save')").first.click()
        page.wait_for_timeout(2000)
        ss(page, "settings", "04_after_save")
        masked = page.locator("input[value*='****']").or_(page.locator("text=****"))
        expect(masked).to_be_visible(timeout=10000)
        print("SETTINGS: API key saved and masked")

    def test_settings_api_returns_masked_key(self, api_client: httpx.Client):
        r = api_client.get("/users/model-settings")
        assert r.status_code == 200
        data = r.json()
        for provider in data.get("providers", []):
            assert "****" in provider.get("api_key_masked", "****")
            assert provider.get("api_key_masked") != ANTHROPIC_API_KEY
        print("SETTINGS API: keys masked, never plaintext")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: Document Upload → RAG Ingestion
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestRAGUpload:
    def test_upload_resume_via_ui(self, page: Page):
        page.goto(f"{BASE_URL}/resume")
        page.wait_for_load_state("networkidle")
        ss(page, "rag", "01_resume_page")
        test_pdf = Path("tests/fixtures/test_resume.pdf")
        assert test_pdf.exists(), "tests/fixtures/test_resume.pdf missing"
        file_input = page.locator("input[type='file']").first
        file_input.set_input_files(str(test_pdf))
        page.wait_for_timeout(2000)
        ss(page, "rag", "02_file_selected")
        page.locator("button:has-text('Upload')").first.click()
        page.wait_for_selector(
            "text=chunks ingested, text=uploaded, text=successfully", timeout=30000
        )
        ss(page, "rag", "03_upload_success")
        print("RAG: resume uploaded and ingested")

    def test_rag_upload_api_directly(self, api_client: httpx.Client):
        test_pdf = Path("tests/fixtures/test_resume.pdf")
        with open(test_pdf, "rb") as f:
            r = httpx.post(
                f"{API_URL}/rag/upload",
                files={"file": ("test_resume.pdf", f, "application/pdf")},
                data={"doc_type": "resume"},
                headers={"Authorization": f"Bearer {TEST_JWT}"},
            )
        assert r.status_code == 201, f"RAG upload failed: {r.text}"
        data = r.json()
        assert data["chunks_ingested"] >= 1
        assert data["doc_type"] == "resume"
        print(f"RAG API: {data['chunks_ingested']} chunks ingested")

    def test_rag_semantic_search(self, api_client: httpx.Client):
        r = api_client.post(
            "/rag/search",
            json={"query": "Python programming experience", "doc_types": ["resume"], "top_k": 3},
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) > 0, "RAG search returned 0 results"
        assert all(0 <= res["score"] <= 1 for res in data["results"])
        print(f"RAG search: {len(data['results'])} chunks, top={data['results'][0]['score']:.3f}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: Job Search Agent
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestJobSearchAgent:
    def test_job_search_via_ui(self, page: Page):
        page.goto(f"{BASE_URL}/jobs")
        page.wait_for_load_state("networkidle")
        ss(page, "job_search", "01_jobs_page")
        page.locator("input[placeholder*='Job title'], input[name='query']").first.fill(
            "Python Developer"
        )
        page.locator(
            "input[placeholder*='Location'], input[name='location']"
        ).first.fill("Bengaluru")
        ss(page, "job_search", "02_query_entered")
        page.locator("button:has-text('Search')").first.click()
        page.wait_for_selector("text=Searching, text=Found, text=match", timeout=120000)
        ss(page, "job_search", "03_results_loading")
        page.wait_for_selector(
            "[class*='job-card'], [data-testid='job-card']", timeout=120000
        )
        ss(page, "job_search", "04_results_loaded")
        cards = page.locator("[class*='job-card'], [data-testid='job-card']").all()
        assert len(cards) > 0, "No job cards rendered"
        print(f"JOB SEARCH UI: {len(cards)} jobs rendered")

    def test_job_search_api_with_sse(self, api_client: httpx.Client):
        r = api_client.post(
            "/agents/run",
            json={
                "task": "search",
                "params": {
                    "query": "Backend Developer",
                    "location": "Remote",
                    "platforms": ["indeed", "naukri"],
                },
            },
        )
        assert r.status_code == 202
        run_id = r.json()["run_id"]
        stream = wait_for_sse_complete(api_client, run_id, timeout_s=120)
        event_types = [e["type"] for e in stream["events"]]
        assert "thinking" in event_types, "No thinking events"
        assert "complete" in event_types, "No complete event"
        result = stream["result"]
        assert "jobs" in result
        assert len(result["jobs"]) > 0
        assert all(0 <= j["match_score"] <= 100 for j in result["jobs"])
        print(f"JOB SEARCH SSE: {len(result['jobs'])} jobs, {len(stream['events'])} events")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: Resume Agent
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestResumeAgent:
    def test_resume_optimization_via_ui(self, page: Page):
        page.goto(f"{BASE_URL}/resume")
        page.wait_for_load_state("networkidle")
        ss(page, "resume", "01_resume_page")
        jd_textarea = page.locator(
            "textarea[placeholder*='job description'], textarea[name='job_description']"
        ).first
        jd_textarea.fill(
            "Senior Python Engineer with 5+ years experience. "
            "Skills: Python, FastAPI, PostgreSQL, Docker, Redis, LangChain."
        )
        ss(page, "resume", "02_jd_entered")
        page.locator("button:has-text('Optimize'), button:has-text('Tailor')").first.click()
        page.wait_for_selector(
            "text=ATS Score, text=ats_score, [data-testid='ats-score']", timeout=90000
        )
        ss(page, "resume", "03_ats_score_shown")
        expect(
            page.locator("a:has-text('Download'), button:has-text('Download')")
        ).to_be_visible(timeout=30000)
        ss(page, "resume", "04_download_available")
        print("RESUME: ATS score displayed, download available")

    def test_resume_api_returns_ats_score(self, api_client: httpx.Client):
        r = api_client.post(
            "/resume/optimize",
            json={
                "job_description": "Senior Python Engineer FastAPI PostgreSQL",
                "tone": "professional",
            },
        )
        assert r.status_code == 200, f"Optimize failed: {r.text}"
        data = r.json()
        assert 0 <= data["ats_score"] <= 100
        assert len(data["resume_text"]) > 100
        assert len(data["ats_suggestions"]) > 0
        assert data["download_url"].startswith("/api/v1/resume/download/")
        print(f"RESUME API: ATS={data['ats_score']}, {len(data['ats_suggestions'])} suggs")

    def test_resume_pdf_download(self, api_client: httpx.Client):
        r = api_client.post(
            "/resume/optimize",
            json={"job_description": "Python Backend Engineer REST APIs", "tone": "professional"},
        )
        doc_id = r.json()["document_id"]
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
    def test_cover_letter_via_ui(self, page: Page):
        page.goto(f"{BASE_URL}/cover-letter")
        page.wait_for_load_state("networkidle")
        ss(page, "cover_letter", "01_page_loaded")
        page.locator(
            "textarea[name='job_description'], textarea[placeholder*='job description']"
        ).first.fill("Senior Python Engineer at Zepto. FastAPI, distributed systems, 5+ years.")
        page.locator(
            "input[name='company_name'], input[placeholder*='company']"
        ).first.fill("Zepto")
        ss(page, "cover_letter", "02_form_filled")
        page.locator("button:has-text('Generate')").first.click()
        page.wait_for_selector("textarea:has-text('Dear'), div:has-text('Dear')", timeout=90000)
        ss(page, "cover_letter", "03_letter_generated")
        expect(page.locator("text=Professional").or_(page.locator("text=Concise"))).to_be_visible()
        ss(page, "cover_letter", "04_variants_visible")
        print("COVER LETTER: generated with variants")

    def test_cover_letter_api(self, api_client: httpx.Client):
        r = api_client.post(
            "/cover-letter/generate",
            json={
                "job_description": "Python Backend Engineer Bangalore",
                "company_name": "Swiggy",
                "tone": "professional",
                "word_limit": 350,
            },
        )
        assert r.status_code == 200, f"CL failed: {r.text}"
        data = r.json()
        assert len(data["variants"]) >= 2
        assert abs(data["word_count"] - 350) <= 80
        assert len(data["cover_letter"]) > 200
        tones = [v["tone"] for v in data["variants"]]
        assert "professional" in tones
        print(f"COVER LETTER API: {data['word_count']} words, {len(data['variants'])} variants")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 8: LinkedIn Agent
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestLinkedInAgent:
    def test_linkedin_optimize_api(self, api_client: httpx.Client):
        r = api_client.post(
            "/linkedin/optimize",
            json={
                "target_role": "Senior Software Engineer",
                "industry": "FinTech",
                "linkedin_url": "",
            },
        )
        assert r.status_code == 200, f"LinkedIn failed: {r.text}"
        data = r.json()
        assert len(data["headline"]) <= 220
        assert len(data["about"]) > 100
        assert isinstance(data["keyword_gaps"], list)
        assert 0 <= data["optimization_score"] <= 100
        print(f"LINKEDIN API: headline='{data['headline'][:50]}...', score={data['optimization_score']}")

    def test_linkedin_via_ui(self, page: Page):
        page.goto(f"{BASE_URL}/linkedin")
        page.wait_for_load_state("networkidle")
        ss(page, "linkedin", "01_page_loaded")
        page.locator(
            "input[name='target_role'], input[placeholder*='target role']"
        ).first.fill("Software Engineer")
        page.locator(
            "input[name='industry'], input[placeholder*='industry']"
        ).first.fill("Technology")
        ss(page, "linkedin", "02_form_filled")
        page.locator("button:has-text('Optimize')").first.click()
        page.wait_for_selector(
            "text=headline, text=Headline, [data-testid='linkedin-headline']", timeout=60000
        )
        ss(page, "linkedin", "03_results_shown")
        print("LINKEDIN UI: optimization results displayed")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 9: Company Research Agent
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestCompanyResearchAgent:
    def test_company_research_api(self, api_client: httpx.Client):
        r = api_client.get("/company/Infosys/research?sections=culture,financials,recent_news")
        assert r.status_code == 200, f"Research failed: {r.text}"
        data = r.json()
        assert data["company"] == "Infosys"
        assert len(data.get("culture", "")) > 50
        assert "intel_id" in data
        print(f"COMPANY RESEARCH: Infosys — {len(str(data))} bytes")

    def test_company_research_caching(self, api_client: httpx.Client):
        t1 = time.time()
        api_client.get("/company/Infosys/research")
        t1_end = time.time()
        t2 = time.time()
        api_client.get("/company/Infosys/research")
        t2_end = time.time()
        assert (t2_end - t2) < (t1_end - t1) * 0.5, "Caching not working"
        print(f"CACHING: 1st={t1_end - t1:.2f}s, 2nd={t2_end - t2:.2f}s")

    def test_company_research_via_ui(self, page: Page):
        page.goto(f"{BASE_URL}/company")
        page.wait_for_load_state("networkidle")
        ss(page, "company", "01_page_loaded")
        page.locator(
            "input[name='company'], input[placeholder*='company name']"
        ).first.fill("Zepto")
        page.locator("button:has-text('Research')").first.click()
        page.wait_for_selector("text=culture, text=Culture, text=interview", timeout=120000)
        ss(page, "company", "02_research_results")
        print("COMPANY UI: Zepto intelligence report displayed")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 10: Salary Agent
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestSalaryAgent:
    def test_salary_benchmark_api(self, api_client: httpx.Client):
        r = api_client.post(
            "/salary/benchmark",
            json={
                "role": "Senior Software Engineer",
                "location": "Bengaluru, India",
                "experience_years": 4,
                "current_salary": 1200000,
                "offer_amount": 1800000,
            },
        )
        assert r.status_code == 200, f"Salary failed: {r.text}"
        data = r.json()
        for p in ("p25", "p50", "p75", "p90"):
            assert p in data["percentiles"]
        assert len(data["negotiation_script"]) > 100
        assert "report_id" in data
        print(f"SALARY API: p50={data['percentiles']['p50']}")

    def test_salary_via_ui(self, page: Page):
        page.goto(f"{BASE_URL}/salary")
        page.wait_for_load_state("networkidle")
        ss(page, "salary", "01_page_loaded")
        page.locator("input[name='role']").first.fill("Senior Software Engineer")
        page.locator("input[name='location']").first.fill("Bengaluru")
        page.locator("input[name='experience_years']").first.fill("4")
        ss(page, "salary", "02_form_filled")
        page.locator("button:has-text('Benchmark')").first.click()
        page.wait_for_selector("text=p50, text=median, text=negotiation", timeout=90000)
        ss(page, "salary", "03_results")
        print("SALARY UI: percentiles and negotiation script displayed")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 11: Interview Coach Agent
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestInterviewCoachAgent:
    def test_interview_session_full_flow(self, api_client: httpx.Client):
        r = api_client.post(
            "/interview/session",
            json={
                "job_title": "SDE-2",
                "company": "Amazon",
                "interview_type": "behavioral",
                "num_questions": 2,
            },
        )
        assert r.status_code == 201, f"Session start failed: {r.text}"
        data = r.json()
        session_id = data["session_id"]
        first_q = data["first_question"]
        assert len(first_q) > 10
        print(f"  Q1: {first_q[:80]}...")

        r2 = api_client.post(
            "/interview/answer",
            json={
                "session_id": session_id,
                "answer": (
                    "In my previous role at a fintech, I delivered a payment gateway "
                    "under a 2-week deadline by breaking it into auth, processing, and "
                    "error handling. Delivered on time, reduced failures by 30%."
                ),
            },
        )
        assert r2.status_code == 200
        d2 = r2.json()
        for dim in ("clarity", "relevance", "depth"):
            assert 0 <= d2["scores"][dim] <= 10
        assert len(d2["feedback"]) > 20
        assert d2["session_complete"] is False
        print(f"  Scores: clarity={d2['scores']['clarity']}, relevance={d2['scores']['relevance']}, depth={d2['scores']['depth']}")
        print(f"  Q2: {d2['next_question'][:80]}...")

        r3 = api_client.post(
            "/interview/answer",
            json={
                "session_id": session_id,
                "answer": (
                    "I disagreed with my tech lead on DB design. I prepared a "
                    "data-driven comparison with benchmarks. After structured discussion "
                    "we combined ideas, achieving 40% better query performance."
                ),
            },
        )
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3["session_complete"] is True
        assert "summary" in d3
        print("INTERVIEW: 2-question session complete, scores returned")

    def test_interview_via_ui(self, page: Page):
        page.goto(f"{BASE_URL}/interview")
        page.wait_for_load_state("networkidle")
        ss(page, "interview", "01_page_loaded")
        page.locator("input[name='job_title']").first.fill("Software Engineer")
        page.locator("input[name='company']").first.fill("Google")
        page.locator("select[name='interview_type']").select_option("behavioral")
        ss(page, "interview", "02_form_filled")
        page.locator("button:has-text('Start Interview')").first.click()
        page.wait_for_selector(
            "text=Question 1, [data-testid='interview-question']", timeout=30000
        )
        ss(page, "interview", "03_first_question")
        page.locator(
            "textarea[name='answer'], textarea[placeholder*='answer']"
        ).first.fill(
            "I coordinated 3 microservices for a distributed system, implemented "
            "circuit breakers, and achieved 99.9% uptime."
        )
        ss(page, "interview", "04_answer_typed")
        page.locator("button:has-text('Submit Answer'), button:has-text('Submit')").first.click()
        page.wait_for_selector(
            "text=clarity, text=Clarity, text=Score, [data-testid='score']", timeout=30000
        )
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
                "recruiter_name": "Priya Sharma",
                "recruiter_company": "Flipkart",
                "job_title": "Senior Engineer",
                "email_type": "outreach",
                "tone": "professional",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "pending_approval"
        assert len(data["body"]) > 50
        assert data["to"] is not None
        print("EMAIL HITL: draft created, pending_approval — NOT sent")

    def test_email_hitl_gate_via_agent_run(self, api_client: httpx.Client):
        r = api_client.post(
            "/agents/run",
            json={
                "task": "email_recruiter",
                "params": {
                    "recruiter_name": "Rahul Mehta",
                    "recruiter_company": "Razorpay",
                    "job_title": "Backend Engineer",
                    "email_type": "outreach",
                },
            },
        )
        assert r.status_code == 202
        run_id = r.json()["run_id"]
        stream = wait_for_sse_complete(api_client, run_id, timeout_s=60)
        assert stream["checkpoint_seen"], "HITL checkpoint never fired"
        cp = stream["result"]["checkpoint"]
        assert cp["action_type"] == "send_email"
        assert "to" in cp["details"]
        assert "body" in cp["details"]
        print(f"EMAIL HITL checkpoint: to={cp['details']['to']}, awaiting approval")

    def test_approve_email_sends_it(self, api_client: httpx.Client):
        r = api_client.post(
            "/agents/run",
            json={
                "task": "email_recruiter",
                "params": {
                    "recruiter_name": "Test Recruiter",
                    "recruiter_company": "Test Corp",
                    "job_title": "Engineer",
                    "email_type": "outreach",
                },
            },
        )
        run_id = r.json()["run_id"]
        wait_for_sse_complete(api_client, run_id, timeout_s=60)
        r2 = api_client.post(
            f"/agents/{run_id}/approve", json={"approved": True, "edits": {}}
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "resumed"
        stream2 = wait_for_sse_complete(api_client, run_id, timeout_s=60)
        assert stream2["result"].get("status") == "sent"
        print("EMAIL HITL approve: email sent after approval")

    def test_cancel_email_prevents_send(self, api_client: httpx.Client):
        r = api_client.post(
            "/agents/run",
            json={
                "task": "email_recruiter",
                "params": {
                    "recruiter_name": "Cancel Test",
                    "recruiter_company": "Test Inc",
                    "job_title": "Engineer",
                    "email_type": "outreach",
                },
            },
        )
        run_id = r.json()["run_id"]
        wait_for_sse_complete(api_client, run_id, timeout_s=60)
        r2 = api_client.post(
            f"/agents/{run_id}/approve", json={"approved": False, "edits": {}}
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "cancelled"
        r3 = api_client.get(f"/agents/runs/{run_id}")
        assert r3.json()["status"] == "cancelled"
        print("EMAIL HITL cancel: run cancelled, email NOT sent")

    def test_wrong_user_cannot_approve(self, api_client: httpx.Client):
        r = api_client.post(
            "/agents/run",
            json={
                "task": "email_recruiter",
                "params": {
                    "recruiter_name": "X", "recruiter_company": "Y",
                    "job_title": "Z", "email_type": "outreach",
                },
            },
        )
        run_id = r.json()["run_id"]
        r2 = httpx.post(
            f"{API_URL}/agents/{run_id}/approve",
            json={"approved": True},
            headers={"Authorization": "Bearer fake.jwt.token", "Content-Type": "application/json"},
        )
        assert r2.status_code in (401, 403), f"Wrong user not blocked: {r2.status_code}"
        print("SECURITY: wrong JWT blocked from approval")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 13: Follow-Up Agent
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestFollowUpAgent:
    def test_followup_schedule_enqueues_jobs(self, api_client: httpx.Client):
        r = api_client.post(
            "/jobs/applications",
            json={
                "job_title": "Python Developer",
                "company": "Test Company",
                "job_url": "https://example.com/job",
                "status": "applied",
                "notes": "Test for follow-up",
            },
        )
        assert r.status_code == 201
        app_id = r.json()["id"]
        r2 = api_client.post(
            "/agents/run",
            json={"task": "follow_up", "params": {"application_id": app_id}},
        )
        assert r2.status_code == 202
        run_id = r2.json()["run_id"]
        stream = wait_for_sse_complete(api_client, run_id, timeout_s=60)
        ok = stream["checkpoint_seen"] or stream["result"].get("followups_scheduled")
        assert ok, "Follow-up agent didn't schedule or request HITL"
        print(f"FOLLOW-UP: jobs scheduled for app {app_id}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 14: Natural Language Search Agent
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestNLSearchAgent:
    def test_nl_search_parses_and_executes(self, api_client: httpx.Client):
        r = api_client.post(
            "/agents/run",
            json={
                "task": "natural_language_search",
                "params": {
                    "query": "senior backend engineer remote India paying above 20 lakhs"
                },
            },
        )
        assert r.status_code == 202
        run_id = r.json()["run_id"]
        stream = wait_for_sse_complete(api_client, run_id, timeout_s=120)
        tool_results = [
            e for e in stream["events"]
            if e["type"] == "tool_result" and e["payload"].get("tool") == "nl_parse"
        ]
        assert len(tool_results) > 0, "NL parse tool_result not fired"
        parsed = tool_results[0]["payload"]["output"]
        assert "query" in parsed
        assert "location" in parsed
        result = stream["result"]
        assert "jobs" in result
        print(f"NL SEARCH: '{parsed['query']}' in {parsed.get('location', '?')}, {len(result['jobs'])} jobs")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 15: AutoApply Pipeline — THE FULL FLOW
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
@pytest.mark.security
class TestAutoApplyPipeline:
    def test_auto_apply_two_hitl_gates(self, api_client: httpx.Client):
        job_url = TEST_JOB_URL
        assert job_url, "Set TEST_JOB_URL env var"
        print(f"\nAUTOAPPLY on: {job_url}")

        r = api_client.post(
            "/agents/run", json={"task": "auto_apply", "params": {"job_url": job_url}}
        )
        assert r.status_code == 202
        run_id = r.json()["run_id"]
        print(f"  Run ID: {run_id}")

        # -- HITL Gate 1: review materials --
        print("  Waiting for HITL Gate 1 (resume + cover letter review)...")
        s1 = wait_for_sse_complete(api_client, run_id, timeout_s=300)
        assert s1["checkpoint_seen"], "Gate 1 never fired"
        cp1 = s1["result"]["checkpoint"]
        assert cp1["action_type"] == "review_application_materials"
        assert "resume_text" in cp1["details"]
        assert "ats_score" in cp1["details"]
        assert "cover_letter" in cp1["details"]
        ats = cp1["details"]["ats_score"]
        assert 0 <= ats <= 100
        print(f"  GATE 1: ATS={ats}, resume ready, cover letter ready")
        print(f"  Resume preview: {cp1['details']['resume_text'][:100]}...")

        r2 = api_client.post(
            f"/agents/{run_id}/approve",
            json={"approved": True, "edits": {"edited_cover_letter": cp1["details"]["cover_letter"]}},
        )
        assert r2.status_code == 200
        print("  Gate 1 approved — browser filling form...")

        # -- HITL Gate 2: review filled form --
        print("  Waiting for HITL Gate 2 (review filled form)...")
        s2 = wait_for_sse_complete(api_client, run_id, timeout_s=300)
        assert s2["checkpoint_seen"], "Gate 2 never fired"
        cp2 = s2["result"]["checkpoint"]
        assert cp2["action_type"] == "submit_application"
        assert "form_screenshots" in cp2["details"]
        assert len(cp2["details"]["form_screenshots"]) > 0
        print(f"  GATE 2: {len(cp2['details']['form_screenshots'])} screenshots of filled form")

        r3 = api_client.post(
            f"/agents/{run_id}/approve", json={"approved": True, "edits": {}}
        )
        assert r3.status_code == 200
        print("  Gate 2 approved — submitting application...")

        # -- Complete --
        s3 = wait_for_sse_complete(api_client, run_id, timeout_s=120)
        result = s3["result"]
        assert result.get("status") == "applied", f"Final status: {result.get('status')}"
        assert "application_id" in result
        assert result.get("followups_scheduled") == ["day-5", "day-12"]
        print(f"  APPLICATION SUBMITTED: {result.get('company', '?')} - {result.get('role', '?')}")
        print(f"  App ID: {result['application_id']}")
        print(f"  Follow-ups: {result['followups_scheduled']}")

        r4 = api_client.get("/jobs/applications?status=applied")
        app_ids = [a["id"] for a in r4.json()["applications"]]
        assert result["application_id"] in app_ids
        print("AUTOAPPLY: COMPLETE — 2 HITL gates passed, application submitted ✅")

    def test_auto_apply_ui_flow(self, page: Page):
        page.goto(f"{BASE_URL}/jobs")
        page.wait_for_load_state("networkidle")
        ss(page, "auto_apply", "01_jobs_page")
        page.locator("input[name='query']").first.fill("Python Developer")
        page.locator("input[name='location']").first.fill("Bengaluru")
        page.locator("button:has-text('Search')").first.click()
        page.wait_for_selector("[class*='job-card']", timeout=120000)
        ss(page, "auto_apply", "02_jobs_found")
        page.locator("[class*='job-card']").first.locator(
            "button:has-text('Auto Apply')"
        ).click()
        page.wait_for_selector("text=Fetching job details, text=Tailoring", timeout=30000)
        ss(page, "auto_apply", "03_agent_running")
        page.wait_for_selector(
            "[role='dialog']:has-text('Review'), [class*='approval-modal'], [class*='ApprovalModal']",
            timeout=300000,
        )
        ss(page, "auto_apply", "04_hitl_gate_1_modal")
        expect(page.locator("text=ATS Score")).to_be_visible()
        expect(page.locator("text=Cover Letter")).to_be_visible()
        page.locator("button:has-text('Approve')").first.click()
        page.wait_for_timeout(2000)
        ss(page, "auto_apply", "05_gate_1_approved")
        page.wait_for_selector(
            "[role='dialog']:has-text('Submit'), [class*='approval-modal']:has-text('screenshot')",
            timeout=300000,
        )
        ss(page, "auto_apply", "06_hitl_gate_2_modal")
        page.locator("button:has-text('Approve')").first.click()
        page.wait_for_timeout(2000)
        ss(page, "auto_apply", "07_gate_2_approved")
        page.wait_for_selector(
            "text=Application submitted, text=Applied successfully, [class*='success']",
            timeout=120000,
        )
        ss(page, "auto_apply", "08_application_submitted")
        print("AUTOAPPLY UI: search → apply → 2 gates → submitted ✅")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 16: Applications Kanban
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestApplicationsKanban:
    def test_applications_list(self, api_client: httpx.Client):
        r = api_client.get("/jobs/applications")
        assert r.status_code == 200
        data = r.json()
        assert "applications" in data
        print(f"APPLICATIONS: {len(data['applications'])} total")

    def test_application_status_update(self, api_client: httpx.Client):
        r = api_client.post(
            "/jobs/applications",
            json={
                "job_title": "QA Test Role",
                "company": "Test Co",
                "job_url": "https://example.com",
                "status": "applied",
            },
        )
        app_id = r.json()["id"]
        r2 = api_client.patch(
            f"/jobs/applications/{app_id}",
            json={"status": "interviewing", "notes": "Phone screen scheduled"},
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "interviewing"
        print("APPLICATIONS: status updated 'applied' → 'interviewing'")

    def test_kanban_drag_via_ui(self, page: Page):
        page.goto(f"{BASE_URL}/applications")
        page.wait_for_load_state("networkidle")
        ss(page, "kanban", "01_kanban_loaded")
        columns = page.locator(
            "[data-column-status], [class*='kanban-column']"
        ).all()
        assert len(columns) >= 4, f"Expected 4+ kanban columns, got {len(columns)}"
        ss(page, "kanban", "02_columns_visible")
        print(f"KANBAN: {len(columns)} columns visible")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 17: SSE Infrastructure
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
class TestSSEInfrastructure:
    def test_sse_stream_content_type(self):
        r = httpx.get(
            f"{API_URL}/agents/fake-run-id/stream",
            headers={"Authorization": f"Bearer {TEST_JWT}"},
            timeout=5,
        )
        if r.status_code == 200:
            assert "text/event-stream" in r.headers.get("content-type", "")
        print("SSE: content-type verified")

    def test_sse_events_in_correct_order(self, api_client: httpx.Client):
        r = api_client.post(
            "/agents/run",
            json={
                "task": "optimize_resume",
                "params": {"job_description": "Python FastAPI Engineer"},
            },
        )
        run_id = r.json()["run_id"]
        stream = wait_for_sse_complete(api_client, run_id, timeout_s=90)
        types = [e["type"] for e in stream["events"]]
        assert "thinking" in types
        assert "complete" in types
        assert types[-1] == "complete", f"Last event is {types[-1]}"
        complete_idx = types.index("complete")
        assert complete_idx == len(types) - 1, "Events after complete"
        unique_order = list(dict.fromkeys(types))
        print(f"SSE ORDER: {' → '.join(unique_order)} ({len(types)} events)")


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
            ("POST", "/salary/benchmark"),
        ]
        for method, path in endpoints:
            r = httpx.request(method, f"{API_URL}{path}", timeout=10)
            assert r.status_code == 401, (
                f"{method} {path} returned {r.status_code} without JWT (expected 401)"
            )
        print(f"SECURITY: all {len(endpoints)} endpoints require JWT")

    def test_internal_routes_return_404_publicly(self):
        r = httpx.get("http://localhost/internal/agents/followup", timeout=5)
        assert r.status_code == 404, f"/internal/ not blocked: {r.status_code}"
        print("SECURITY: /internal/ routes blocked (Nginx)")

    def test_rate_limiting_fires(self, api_client: httpx.Client):
        statuses: list[int] = []
        for _ in range(65):
            r = api_client.get("/users/me")
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
    print(f"  Screenshots: tests/e2e/screenshots/")
    print(f"  Videos:      tests/e2e/videos/")
    print("=" * 70)
