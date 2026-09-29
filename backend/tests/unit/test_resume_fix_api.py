"""GET /resume/tailored/{id} and POST /resume/tailored/{id}/fix."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

SPARSE_RESUME = """# Jane Doe
jane@example.com
## SUMMARY
AI engineer building LLM tools.
## EXPERIENCE
### Prompt Engineer Intern | Agentic Universe (Qultured Media Pvt.
- Built prompt evaluation pipelines in Python
## SKILLS
**Languages:** Python, SQL
"""

FULL_EMPLOYER = "Agentic Universe (Qultured Media Pvt. Ltd.)"
FIXED_HEADING = (
    f"### Prompt Engineer Intern | {FULL_EMPLOYER} | Remote | Jun 2025 - Present"
)

FULL_FIX = {
    "contact": {"phone": "+91 98765 43210", "location": "Pune, India"},
    "experience": [{
        "index": 0,
        "employer": FULL_EMPLOYER,
        "location": "Remote",
        "start": "Jun 2025",
        "end": "Present",
    }],
    "education": [{
        "degree": "B.Tech Computer Science",
        "institution": "Savitribai Phule Pune University",
        "start": "Aug 2021",
        "end": "May 2025",
    }],
}

DATES_WARNING = "Employment dates were not provided for the internship."
EDUCATION_WARNING = "No education section was found in the source resume."
AZURE_WARNING = "The JD asks for Azure experience, which the resume does not show."


def _doc(user_id, *, raw_text=SPARSE_RESUME, ats_data=None):
    from app.models.db import UserDocument

    return UserDocument(
        id=uuid.uuid4(),
        user_id=user_id,
        doc_type="resume_tailored",
        filename="resume.pdf",
        storage_path="u/resume.pdf",
        raw_text=raw_text,
        ats_score=70,
        ats_data={"template": "modern", "summary": "Tailored.", **(ats_data or {})},
    )


def _build_app() -> tuple[FastAPI, bool]:
    """The real app when it imports (it needs temporalio); otherwise a minimal
    app hosting only the resume router, configured the way app.main does."""
    try:
        from app.main import app

        return app, True
    except ModuleNotFoundError:
        from slowapi import _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded

        from app.api.v1.resume import router
        from app.core.rate_limit import limiter

        app = FastAPI()
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.include_router(router, prefix="/api/v1")
        return app, False


class _Harness:
    def __init__(self, monkeypatch, doc, *, user_id=None, facts_row=None):
        self.doc = doc
        self.user_id = user_id or (doc.user_id if doc is not None else uuid.uuid4())
        self.facts_row = facts_row
        self.uploaded: list[tuple] = []
        self.deleted: list[tuple] = []
        self.saved_facts: list[tuple] = []
        self.rendered: list[str] = []
        self.ats_calls: list[tuple] = []
        self.flushes = 0

        from app.core.rate_limit import limiter
        from app.services import pdf_service

        limiter.reset()
        real_render = pdf_service.generate_resume_pdf

        def render(text, full_name="", template="modern"):
            self.rendered.append(template)
            return real_render(text, full_name=full_name, template=template)

        def upload_file(user_id, filename, data, content_type):
            assert data.startswith(b"%PDF")
            self.uploaded.append((user_id, filename, content_type))
            return "user-id/new.pdf"

        def delete_file(path, user_id):
            self.deleted.append((path, user_id))

        async def load_facts_row(db, user_id):
            return self.facts_row

        async def load_profile(db, user_id):
            return None

        async def save_facts(db, user_id, facts):
            self.saved_facts.append((user_id, facts))

        class _Ats:
            composite_score = 91
            missing_keywords = ["Azure"]

        def compute_ats_score(resume_text, jd_text):
            self.ats_calls.append((resume_text, jd_text))
            return _Ats()

        monkeypatch.setattr("app.services.pdf_service.generate_resume_pdf", render)
        monkeypatch.setattr("app.services.storage_service.upload_file", upload_file)
        monkeypatch.setattr("app.services.storage_service.delete_file", delete_file)
        monkeypatch.setattr("app.services.resume_facts.load_facts_row", load_facts_row)
        monkeypatch.setattr("app.services.resume_facts.load_profile", load_profile)
        monkeypatch.setattr("app.services.resume_facts.save_facts", save_facts)
        monkeypatch.setattr("app.services.ats_service.compute_ats_score", compute_ats_score)

        self.app, is_main = _build_app()
        if is_main:
            monkeypatch.setattr("app.main.verify_token", lambda token: {"sub": "user-1"})

    def _db(self):
        harness = self

        class _Result:
            def __init__(self, value):
                self._value = value

            def scalar_one_or_none(self):
                return self._value

        class _FakeDB:
            async def execute(self, stmt, *a, **k):
                # Honour the query's id/user filters so ownership is exercised.
                params = set(stmt.compile().params.values())
                doc = harness.doc
                if doc is None or doc.id not in params or doc.user_id not in params:
                    return _Result(None)
                return _Result(doc)

            async def flush(self):
                harness.flushes += 1

        return _FakeDB()

    async def request(self, method, document_id=None, json=None):
        from app.api.v1.deps import get_current_user, get_db
        from app.models.db import User

        db = self._db()

        async def _fake_db():
            return db

        self.app.dependency_overrides[get_db] = _fake_db
        self.app.dependency_overrides[get_current_user] = lambda: User(
            id=self.user_id, email="jane@example.com", full_name="Jane Doe"
        )
        doc_id = document_id or str(self.doc.id)
        path = f"/api/v1/resume/tailored/{doc_id}"
        if method == "POST":
            path += "/fix"
        try:
            transport = ASGITransport(app=self.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(
                    method, path, json=json, headers={"Authorization": "Bearer t"}
                )
        finally:
            self.app.dependency_overrides.clear()

    async def fix(self, body, document_id=None):
        return await self.request("POST", document_id, json=body)

    async def get(self, document_id=None):
        return await self.request("GET", document_id)


# ── GET ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_returns_review_with_issues_for_sparse_doc(monkeypatch):
    doc = _doc(uuid.uuid4(), ats_data={"keywords_matched": ["Python"]})
    h = _Harness(monkeypatch, doc)

    resp = await h.get()

    assert resp.status_code == 200
    body = resp.json()
    assert body["document_id"] == str(doc.id)
    assert body["template"] == "modern"
    assert body["resume_markdown"] == SPARSE_RESUME
    assert body["summary"] == "Tailored."
    assert body["ats_score"] == 70
    assert body["keywords_matched"] == ["Python"]
    codes = {i["code"] for i in body["review"]["issues"]}
    assert codes == {"missing_phone", "truncated_employer", "missing_dates", "missing_education"}
    assert body["review"]["contact"]["email"] == "jane@example.com"
    assert body["review"]["has_education_section"] is False
    [entry] = body["review"]["experience"]
    assert entry["index"] == 0
    assert entry["role"] == "Prompt Engineer Intern"
    assert set(entry["issues"]) == {"truncated_employer", "missing_dates"}
    # Pre-fill falls back to the login email when no profile/facts exist.
    assert body["contact_suggestions"]["email"] == "jane@example.com"
    # Reading must not write anything.
    assert h.uploaded == [] and h.deleted == [] and h.rendered == []


# ── POST fix ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fix_resolves_all_issues_and_remembers_facts(monkeypatch):
    doc = _doc(uuid.uuid4())
    h = _Harness(monkeypatch, doc)

    resp = await h.fix({**FULL_FIX, "remember": True})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["review"]["issues"] == []
    assert FIXED_HEADING in body["resume_markdown"]
    assert "jane@example.com | +91 98765 43210 | Pune, India" in body["resume_markdown"]
    assert "## EDUCATION" in body["resume_markdown"]
    assert body["review"]["has_education_section"] is True
    assert body["template"] == "modern"

    # Document updated in place with the new text and re-rendered PDF.
    assert doc.raw_text == body["resume_markdown"]
    assert doc.storage_path == "user-id/new.pdf"
    assert h.rendered == ["modern"]
    assert h.uploaded == [(str(doc.user_id), "resume.pdf", "application/pdf")]
    assert ("u/resume.pdf", str(doc.user_id)) in h.deleted
    assert h.flushes >= 1

    # Facts saved for future tailoring runs.
    [(saved_user, facts)] = h.saved_facts
    assert saved_user == doc.user_id
    assert facts["contact"]["phone"] == "+91 98765 43210"
    [exp] = facts["experience"]
    assert exp["employer"] == FULL_EMPLOYER
    assert exp["employer_match"] == "Agentic Universe (Qultured Media Pvt."
    assert (exp["start"], exp["end"]) == ("Jun 2025", "Present")
    [edu] = facts["education"]
    assert edu["institution"] == "Savitribai Phule Pune University"


@pytest.mark.asyncio
async def test_fix_with_remember_false_does_not_save_facts(monkeypatch):
    doc = _doc(uuid.uuid4())
    h = _Harness(monkeypatch, doc)

    resp = await h.fix({**FULL_FIX, "remember": False})

    assert resp.status_code == 200, resp.text
    assert resp.json()["review"]["issues"] == []
    assert h.saved_facts == []
    assert doc.storage_path == "user-id/new.pdf"
    assert ("u/resume.pdf", str(doc.user_id)) in h.deleted


@pytest.mark.asyncio
async def test_template_only_fix_switches_template(monkeypatch):
    doc = _doc(uuid.uuid4())
    h = _Harness(monkeypatch, doc)

    resp = await h.fix({"template": "classic"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["template"] == "classic"
    assert doc.ats_data["template"] == "classic"
    assert h.rendered == ["classic"]
    # Text is untouched apart from normalisation; the gaps are still reported.
    assert body["resume_markdown"].strip() == SPARSE_RESUME.strip()
    assert {i["code"] for i in body["review"]["issues"]} >= {"missing_dates"}
    assert doc.storage_path == "user-id/new.pdf"


@pytest.mark.asyncio
async def test_fix_rescores_when_jd_is_recorded(monkeypatch):
    doc = _doc(uuid.uuid4(), ats_data={"jd_text": "Python, Azure", "keywords_missing": []})
    h = _Harness(monkeypatch, doc)

    resp = await h.fix({"template": "technical"})

    assert resp.status_code == 200, resp.text
    assert resp.json()["ats_score"] == 91
    assert resp.json()["keywords_missing"] == ["Azure"]
    assert h.ats_calls and h.ats_calls[0][1] == "Python, Azure"


@pytest.mark.asyncio
async def test_bad_experience_index_is_422(monkeypatch):
    doc = _doc(uuid.uuid4())
    h = _Harness(monkeypatch, doc)

    resp = await h.fix({"experience": [{"index": 5, "start": "Jun 2025"}]})

    assert resp.status_code == 422
    assert "index 5" in resp.json()["detail"]
    assert doc.raw_text == SPARSE_RESUME
    assert doc.storage_path == "u/resume.pdf"
    assert h.uploaded == [] and h.deleted == [] and h.saved_facts == []


@pytest.mark.asyncio
async def test_blank_manual_edit_is_422(monkeypatch):
    doc = _doc(uuid.uuid4())
    h = _Harness(monkeypatch, doc)

    resp = await h.fix({"resume_markdown": "   \n  "})

    assert resp.status_code == 422
    assert doc.raw_text == SPARSE_RESUME
    assert h.uploaded == []


@pytest.mark.asyncio
async def test_other_users_document_is_404(monkeypatch):
    doc = _doc(uuid.uuid4())
    h = _Harness(monkeypatch, doc, user_id=uuid.uuid4())

    get_resp = await h.get()
    fix_resp = await h.fix({"template": "classic"})

    assert get_resp.status_code == 404
    assert fix_resp.status_code == 404
    assert doc.ats_data["template"] == "modern"
    assert h.uploaded == [] and h.deleted == []


@pytest.mark.asyncio
@pytest.mark.parametrize("document_id", [None, "not-a-uuid"])
async def test_missing_document_is_404(monkeypatch, document_id):
    h = _Harness(monkeypatch, None)

    target = document_id or str(uuid.uuid4())
    assert (await h.get(target)).status_code == 404
    assert (await h.fix({"template": "classic"}, target)).status_code == 404
    assert h.uploaded == []


@pytest.mark.asyncio
async def test_resolved_warnings_are_filtered_and_skill_gaps_kept(monkeypatch):
    doc = _doc(
        uuid.uuid4(),
        ats_data={"warnings": [DATES_WARNING, EDUCATION_WARNING, AZURE_WARNING]},
    )
    h = _Harness(monkeypatch, doc)

    # Fixing only the dates drops the dates warning; education is still open.
    resp = await h.fix({"experience": [{"index": 0, "start": "Jun 2025", "end": "Present"}]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["warnings"] == [EDUCATION_WARNING, AZURE_WARNING]

    # Adding education resolves the rest; the genuine skill gap stays.
    resp = await h.fix({"education": FULL_FIX["education"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["warnings"] == [AZURE_WARNING]
    assert doc.ats_data["warnings"] == [AZURE_WARNING]
