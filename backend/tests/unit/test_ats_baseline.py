"""Baseline resume scoring: keywords only against jobs the user saved."""

from app.services.ats_service import score_resume_baseline, top_resume_keywords

RESUME = """Priya Raghunathan
priya@example.com | +91 98765 43210

Experience
Backend engineer building payment APIs in Python and PostgreSQL on AWS.
Led a migration of Python services to Kubernetes, cutting deploy time by half.

Education
B.Tech Computer Science

Skills
Python, PostgreSQL, AWS, Kubernetes, Docker
"""

JOBS = """Senior Backend Engineer
Requirements: Python, Kafka, PostgreSQL, Terraform, AWS.
You will design event-driven services with Kafka and manage infrastructure in Terraform.
"""


def test_without_saved_jobs_keywords_are_not_scored():
    score, data = score_resume_baseline(RESUME, None)

    assert data["keyword_basis"] is None
    assert data["keyword_score"] is None
    assert data["missing_keywords"] == []
    assert 0 <= score <= 100
    # The resume's own terms still feed skill and role suggestions.
    assert "python" in data["matched_keywords"]
    assert "example.com" not in data["matched_keywords"]
    assert not any("keyword" in s.lower() for s in data["suggestions"])


def test_saved_jobs_drive_keyword_coverage():
    score, data = score_resume_baseline(RESUME, JOBS)

    assert data["keyword_basis"] == "saved_jobs"
    assert isinstance(data["keyword_score"], int)
    assert {"kafka", "terraform"} <= set(data["missing_keywords"])
    assert "python" in data["matched_keywords"]
    # No placeholder-JD vocabulary leaks into the advice.
    assert not {"candidate", "ideal", "abilities"} & set(data["missing_keywords"])


def test_top_keywords_are_ordered_by_frequency():
    assert top_resume_keywords(RESUME, limit=1) == ["python"]


async def test_legacy_placeholder_scores_are_refreshed_in_the_background(monkeypatch):
    import uuid
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from app.api.v1 import rag
    from app.core import background

    spawned = []

    def fake_spawn(coro):
        spawned.append(coro)
        coro.close()

    monkeypatch.setattr(background, "spawn_background", fake_spawn)
    no_jobs = MagicMock()
    no_jobs.first.return_value = None
    db = MagicMock()
    db.execute = AsyncMock(return_value=no_jobs)

    def doc(ats_data, doc_type="resume"):
        return SimpleNamespace(id=uuid.uuid4(), doc_type=doc_type, raw_text="x", ats_data=ats_data)

    docs = [
        doc({"keyword_score": 40, "missing_keywords": ["candidate"]}),  # legacy placeholder
        doc({"keyword_basis": None, "keyword_score": None}),  # no saved jobs yet
        doc({"keyword_basis": "saved_jobs", "keyword_score": 70}),  # already real
        doc({"keywords_matched": []}, doc_type="resume_tailored"),  # agent output
        doc(None),  # upload scoring still running
    ]
    await rag._refresh_stale_resume_scores(db, uuid.uuid4(), docs)

    assert len(spawned) == 1
