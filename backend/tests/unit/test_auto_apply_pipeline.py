"""Unit tests for Auto Apply Pipeline — multi-step flow, HITL checkpoints, error handling."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_auto_apply_returns_structured_result():
    from app.agents.auto_apply_pipeline import run_auto_apply_pipeline

    with (
        patch("app.agents.auto_apply_pipeline.scrape_jobs", return_value=[]),
        patch("app.agents.auto_apply_pipeline.fetch_model_settings", return_value=MagicMock()),
        patch("app.agents.auto_apply_pipeline.fetch_user_profile_text", return_value=""),
    ):
        result = await run_auto_apply_pipeline(
            user_id=str(uuid.uuid4()),
            search_query="Python engineer",
            location="Remote",
            max_applications=5,
        )

    assert "jobs_found" in result
    assert "jobs_scored" in result
    assert "applications_sent" in result
    assert "errors" in result


def test_score_job_quick_returns_0_100():
    from app.agents.auto_apply_pipeline import _score_job_quick
    from app.services.job_platforms_service import JobListing

    mock_llm = MagicMock()

    job = JobListing(
        title="Senior Python Engineer",
        company="Stripe",
        location="Remote",
        description="Build distributed systems",
        job_url="https://stripe.com/jobs/1",
        platform="linkedin",
    )

    with patch("app.agents.thinking.think_about_job_match", return_value={"match_level": "HIGH", "decision": "YES"}):
        score = _score_job_quick(mock_llm, job, "Profile text")

    assert isinstance(score, int)
    assert 0 <= score <= 100


def test_generate_cold_email_structure():
    from app.agents.auto_apply_pipeline import _generate_cold_email

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content="Subject: Following up\n\nDear team,\n\nI'm reaching out..."
    )

    result = _generate_cold_email(mock_llm, "Recruiter Name", "recruiter@stripe.com", "Stripe", "Engineer", "Job desc", "My profile")
    assert isinstance(result, dict)
    assert "subject" in result
    assert "body" in result


def test_generate_linkedin_note_within_limit():
    from app.agents.auto_apply_pipeline import _generate_linkedin_note

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="Hi, I'm interested in the Engineer role at Stripe. Let's connect!")

    note = _generate_linkedin_note(mock_llm, "Stripe", "Engineer", "Profile")
    assert isinstance(note, str)
    assert len(note) <= 300  # LinkedIn limit
    assert "Stripe" in note
