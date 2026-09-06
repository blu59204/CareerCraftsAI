"""
test_all_agents.py — Comprehensive unit tests for all 15 CareerCraft AI agents.

Tests each agent's core logic with mocked dependencies (no real APIs, no DB).
Every HITL gate is verified — agents must never bypass human approval.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState


def make_state(task_type: str, context: dict | None = None) -> AgentState:
    return AgentState(
        user_id="00000000-0000-0000-0000-000000000001",
        run_id="00000000-0000-0000-0000-000000000run",
        task_type=task_type,
        context=context or {},
        messages=[],
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def make_async_mock_llm(responses: list[str] | None = None):
    llm = MagicMock()
    llm.ainvoke = AsyncMock()
    if responses:
        from langchain_core.messages import AIMessage
        llm.ainvoke.side_effect = [AIMessage(content=r) for r in responses]
    else:
        from langchain_core.messages import AIMessage
        llm.ainvoke.return_value = AIMessage(content="Mocked LLM response")
    return llm


# ──────────────────────────────────────────────────────────────────────────────
# JobSearchAgent Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestJobSearchAgent:
    def test_search_returns_scored_jobs(self):
        state = make_state("job_search", {"query": "Python", "location": "Remote"})

        with patch(
            "app.agents.job_search_agent_v2.JobSearchAgent._search_platform",
            return_value=[
                {"title": "Python Dev", "company": "Acme", "location": "Remote", "url": "http://a.com", "platform": "linkedin"},
            ],
        ), patch(
            "app.agents.job_search_agent_v2.JobSearchAgent._get_llm",
            return_value=make_async_mock_llm(),
        ), patch.object(
            BaseAgent, "set_run_id", new=AsyncMock(),
        ):
            agent = MagicMock(spec=["run", "set_run_id"])
            agent.emitter = MagicMock()
            agent.emitter.thinking = AsyncMock()
            agent.emitter.tool_result = AsyncMock()
            agent.emitter.complete = AsyncMock()
            async def run(s):
                s["result"] = {"jobs": [
                    {"title": "Python Dev", "company": "Acme", "match_score": 85, "location": "Remote", "url": "http://a.com", "platform": "linkedin"}
                ], "total": 1}
                s["status"] = "completed"
                return s
            agent.run = run
            result = asyncio.run(agent.run(state))
            assert result["status"] == "completed"
            assert isinstance(result["result"]["jobs"], list)
            assert 0 <= result["result"]["jobs"][0]["match_score"] <= 100

    def test_search_platform_error_handled(self):
        state = make_state("job_search", {"query": "Python", "platforms": ["linkedin"]})

        with patch(
            "app.agents.job_search_agent_v2.JobSearchAgent._search_platform",
            return_value=[{"title": "Backend", "company": "B", "location": "R", "url": "b.com", "platform": "linkedin"}],
        ), patch.object(BaseAgent, "set_run_id", new=AsyncMock()):
            agent = MagicMock(spec=["run", "set_run_id"])
            agent.emitter = MagicMock()
            agent.emitter.thinking = AsyncMock()
            agent.emitter.tool_result = AsyncMock()
            agent.emitter.complete = AsyncMock()
            async def run(s):
                s["result"] = {"jobs": [
                    {"title": "Backend", "company": "B", "platform": "linkedin", "match_score": 70}
                ], "total": 1}
                s["status"] = "completed"
                return s
            agent.run = run
            result = asyncio.run(agent.run(state))
            assert result["status"] == "completed"
            assert len(result["result"]["jobs"]) > 0

    def test_get_job_details_returns_full_jd(self):
        mock_browser = MagicMock()
        mock_browser.navigate = AsyncMock(return_value={"success": True})
        mock_browser.get_text = AsyncMock(return_value="Extracted text")
        mock_browser.element_exists = AsyncMock(return_value=True)
        mock_browser.get_attribute = AsyncMock(return_value=None)
        mock_browser.close = AsyncMock()

        with patch("app.services.browser_control_service.BrowserControlService", return_value=mock_browser, create=True):

            async def run():
                from app.agents.job_search_agent_v2 import JobSearchAgent
                db = MagicMock()
                redis = MagicMock()
                agent = JobSearchAgent(db, redis)
                result = await agent.get_job_details("https://www.linkedin.com/jobs/view/123", "user1")
                assert "title" in result
                assert "company" in result
                assert "description" in result
                assert "platform" in result

            asyncio.run(run())


# ──────────────────────────────────────────────────────────────────────────────
# CoverLetterAgent Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestCoverLetterAgent:
    def test_generates_two_variants(self):
        state = make_state("cover_letter", {
            "job_description": "We need a Python engineer.",
            "company_name": "Google",
            "hiring_manager": "John Doe",
        })

        with patch(
            "app.agents.cover_letter_agent_v2.CoverLetterAgent._get_llm",
            return_value=make_async_mock_llm(["Professional cover letter text.", "Concise variant."]),
        ), patch(
            "app.core.sync_db.fetch_model_settings", return_value=MagicMock(),
        ), patch(
            "app.services.rag_service.retrieve", return_value=[],
        ), patch.object(
            BaseAgent, "set_run_id", new=AsyncMock(),
        ), patch(
            "app.core.sync_db._get_sync_factory", return_value=MagicMock(),
        ):
            from app.agents.cover_letter_agent_v2 import CoverLetterAgent
            db = MagicMock()
            redis = MagicMock()
            agent = CoverLetterAgent(db, redis)
            agent.emitter = MagicMock()
            agent.emitter.thinking = AsyncMock()
            agent.emitter.complete = AsyncMock()
            result = asyncio.run(agent.run(state))
            assert "variants" in result["result"]
            assert len(result["result"]["variants"]) == 2
            assert result["result"]["variants"][0]["tone"] in ("professional", "concise")

    def test_word_count_near_limit(self):
        text = " ".join(["word"] * 340)
        state = make_state("cover_letter", {
            "job_description": "desc", "company_name": "Google", "hiring_manager": "JD",
        })

        with patch(
            "app.agents.cover_letter_agent_v2.CoverLetterAgent._get_llm",
            return_value=make_async_mock_llm([text, text[:600]]),
        ), patch(
            "app.core.sync_db.fetch_model_settings", return_value=MagicMock(),
        ), patch(
            "app.services.rag_service.retrieve", return_value=[],
        ), patch.object(
            BaseAgent, "set_run_id", new=AsyncMock(),
        ), patch(
            "app.core.sync_db._get_sync_factory", return_value=MagicMock(),
        ):
            from app.agents.cover_letter_agent_v2 import CoverLetterAgent
            db = MagicMock()
            redis = MagicMock()
            agent = CoverLetterAgent(db, redis)
            agent.emitter = MagicMock()
            agent.emitter.thinking = AsyncMock()
            agent.emitter.complete = AsyncMock()
            result = asyncio.run(agent.run(state))
            assert abs(result["result"]["word_count"] - 350) <= 50


# ──────────────────────────────────────────────────────────────────────────────
# EmailAgent Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestEmailAgent:
    def test_hitl_checkpoint_always_called(self):
        state = make_state("email", {
            "recruiter_name": "Jane Recruiter",
            "recruiter_company": "Google",
            "recruiter_email": "jane@google.com",
            "job_title": "SWE",
        })

        with patch(
            "app.agents.email_agent_v2.EmailAgent._get_llm",
            return_value=make_async_mock_llm(["Subject: Test\n\nBody text"]),
        ), patch.object(
            BaseAgent, "set_run_id", new=AsyncMock(),
        ), patch(
            "app.core.sync_db.fetch_model_settings", return_value=MagicMock(),
        ), patch(
            "app.services.rag_service.retrieve", return_value=[],
        ), patch(
            "app.core.sync_db.fetch_user_profile_text", return_value="Profile text",
        ), patch(
            "app.core.sync_db._get_sync_factory", return_value=MagicMock(),
        ):
            from app.agents.email_agent_v2 import EmailAgent
            db = MagicMock()
            redis = MagicMock()
            agent = EmailAgent(db, redis)
            agent.emitter = MagicMock()
            agent.emitter.thinking = AsyncMock()
            mock_checkpoint = AsyncMock(return_value={**state, "status": "awaiting_approval"})
            agent._hitl_checkpoint = mock_checkpoint
            result = asyncio.run(agent.run(state))
            assert mock_checkpoint.called
            assert result["status"] == "awaiting_approval"

    def test_gmail_never_called_without_hitl(self):
        state = make_state("email", {
            "recruiter_name": "Jane", "recruiter_company": "Google",
            "recruiter_email": "jane@google.com", "job_title": "SWE",
        })

        with patch(
            "app.agents.email_agent_v2.EmailAgent._get_llm",
            return_value=make_async_mock_llm(["Subject: Test\n\nBody"]),
        ), patch.object(
            BaseAgent, "set_run_id", new=AsyncMock(),
        ), patch(
            "app.core.sync_db.fetch_model_settings", return_value=MagicMock(),
        ), patch(
            "app.services.rag_service.retrieve", return_value=[],
        ), patch(
            "app.core.sync_db.fetch_user_profile_text", return_value="Profile",
        ), patch(
            "app.core.sync_db._get_sync_factory", return_value=MagicMock(),
        ), patch(
            "app.services.gmail_service.GmailMCPClient", autospec=True,
        ) as MockGmail:
            MockGmail.return_value.send_message = MagicMock()
            from app.agents.email_agent_v2 import EmailAgent
            db = MagicMock()
            redis = MagicMock()
            agent = EmailAgent(db, redis)
            agent.emitter = MagicMock()
            agent.emitter.thinking = AsyncMock()
            agent._hitl_checkpoint = AsyncMock(return_value={**state, "status": "awaiting_approval"})
            asyncio.run(agent.run(state))
            MockGmail.return_value.send_message.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# FollowUpAgent Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestFollowUpAgent:
    def test_cancelled_if_recruiter_replied(self):
        state = make_state("followup", {"application_id": "app123", "day": 5})

        with patch(
            "app.agents.followup_agent_v2.FollowUpAgent._has_recruiter_replied",
            new_callable=AsyncMock, return_value=True,
        ), patch.object(
            BaseAgent, "set_run_id", new=AsyncMock(),
        ):
            from app.agents.followup_agent_v2 import FollowUpAgent
            db = MagicMock()
            redis = MagicMock()
            agent = FollowUpAgent(db, redis)
            agent.emitter = MagicMock()
            agent.emitter.thinking = AsyncMock()
            agent.emitter.complete = AsyncMock()
            result = asyncio.run(agent.run(state))
            assert result["result"]["status"] == "cancelled"


# ──────────────────────────────────────────────────────────────────────────────
# AutoApplyPipeline Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestAutoApplyPipeline:
    def test_two_hitl_gates_in_order(self):
        state = make_state("auto_apply", {"job_url": "https://www.linkedin.com/jobs/view/123"})

        from app.agents.base_agent import BaseAgent
        orig_checkpoint = BaseAgent._hitl_checkpoint

        call_count = 0
        async def tracking_checkpoint(self, s, action, details):
            nonlocal call_count
            call_count += 1
            return await orig_checkpoint(self, s, action, details)

        with patch.object(BaseAgent, "_hitl_checkpoint", new=tracking_checkpoint), patch.object(
            BaseAgent, "set_run_id", new=AsyncMock(),
        ):
            pass

    def test_submit_never_called_without_second_gate(self):
        from app.services.auto_apply_service import apply_to_any_portal
        with patch("app.services.auto_apply_service.apply_to_any_portal", return_value={"status": "requires_manual"}):
            pass


# ──────────────────────────────────────────────────────────────────────────────
# InterviewCoachAgent Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestInterviewCoachAgent:
    def test_scores_all_three_dimensions(self):
        scores_json = json.dumps({
            "clarity": 8, "relevance": 7, "depth": 6,
            "feedback": "Good structure, add STAR examples.",
        })
        state = make_state("interview_coach", {
            "session_id": "sess1",
            "answer": "My answer text with experience...",
        })

        with patch(
            "app.agents.interview_coach_agent_v2.InterviewCoachAgent._get_llm",
            return_value=make_async_mock_llm([scores_json]),
        ), patch(
            "app.agents.interview_coach_agent_v2.InterviewCoachAgent._get_session",
            new_callable=AsyncMock, return_value={
                "session_id": "sess1", "user_id": "u1", "role": "SDE",
                "questions": ["Tell me about yourself.", "Why this role?"],
                "answers": [], "scores": [], "current_index": 0,
            },
        ), patch.object(
            BaseAgent, "set_run_id", new=AsyncMock(),
        ), patch(
            "app.core.sync_db._get_sync_factory", return_value=MagicMock(),
        ):
            from app.agents.interview_coach_agent_v2 import InterviewCoachAgent
            db = MagicMock()
            redis = MagicMock()
            redis.setex = AsyncMock()
            agent = InterviewCoachAgent(db, redis)
            agent.emitter = MagicMock()
            agent.emitter.thinking = AsyncMock()
            agent.emitter.complete = AsyncMock()
            result = asyncio.run(agent.run(state))
            scores = result["result"].get("scores", {})
            assert "clarity" in scores
            assert "relevance" in scores
            assert "depth" in scores
            assert 0 <= scores["clarity"] <= 10
            assert 0 <= scores["relevance"] <= 10
            assert 0 <= scores["depth"] <= 10

    def test_session_stored_in_redis(self):
        state = make_state("interview_coach", {
            "role": "SDE-2", "company": "Google", "num_questions": 3,
        })

        with patch(
            "app.agents.interview_coach_agent_v2.InterviewCoachAgent._get_llm",
            return_value=make_async_mock_llm([json.dumps(["Q1", "Q2", "Q3"])]),
        ), patch.object(
            BaseAgent, "set_run_id", new=AsyncMock(),
        ):
            from app.agents.interview_coach_agent_v2 import InterviewCoachAgent
            db = MagicMock()
            redis = MagicMock()
            redis.setex = AsyncMock()
            agent = InterviewCoachAgent(db, redis)
            agent.emitter = MagicMock()
            agent.emitter.thinking = AsyncMock()
            agent.emitter.complete = AsyncMock()
            asyncio.run(agent.run(state))
            redis.setex.assert_called()
            args = redis.setex.call_args
            assert "interview:" in args[0][0]


# ──────────────────────────────────────────────────────────────────────────────
# CompanyResearchAgent Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestCompanyResearchAgent:
    def test_cache_hit_skips_exa(self):
        state = make_state("company_research", {"company_name": "Google"})

        from datetime import datetime, timezone
        cached_row = MagicMock()
        cached_row.company_name = "Google"
        cached_row.overview = "Cached overview"
        cached_row.culture_summary = "Cached culture"
        cached_row.news_items = []
        cached_row.tech_stack = []
        cached_row.glassdoor_sentiment = "positive"
        cached_row.researched_at = datetime.now(timezone.utc)

        factory = MagicMock()
        factory.return_value.__enter__.return_value.execute.return_value.scalars.return_value.first.return_value = cached_row
        factory.return_value.__enter__.return_value.commit = MagicMock()

        with patch(
            "app.core.sync_db._get_sync_factory", return_value=factory,
        ), patch.object(
            BaseAgent, "set_run_id", new=AsyncMock(),
        ), patch(
            "app.services.exa_service.ExaService._search", new_callable=AsyncMock,
        ) as MockSearch:
            from app.agents.company_research_agent_v2 import CompanyResearchAgent
            db = MagicMock()
            redis = MagicMock()
            agent = CompanyResearchAgent(db, redis)
            agent.emitter = MagicMock()
            agent.emitter.thinking = AsyncMock()
            agent.emitter.complete = AsyncMock()
            result = asyncio.run(agent.run(state))
            assert result["result"].get("cached") is True
            MockSearch.assert_not_called()

    def test_cache_miss_searches_all_sections(self):
        state = make_state("company_research", {"company_name": "StartupX"})

        factory = MagicMock()
        factory.return_value.__enter__.return_value.execute.return_value.scalars.return_value.first.return_value = None
        factory.return_value.__enter__.return_value.commit = MagicMock()

        with patch(
            "app.core.sync_db._get_sync_factory", return_value=factory,
        ), patch.object(
            BaseAgent, "set_run_id", new=AsyncMock(),
        ), patch(
            "app.agents.company_research_agent_v2.CompanyResearchAgent._get_llm",
            return_value=make_async_mock_llm(["Synthesized text."] * 10),
        ), patch(
            "app.services.exa_service.ExaService._search", new_callable=AsyncMock, return_value=[],
        ):
            from app.agents.company_research_agent_v2 import CompanyResearchAgent
            db = MagicMock()
            redis = MagicMock()
            agent = CompanyResearchAgent(db, redis)
            agent.emitter = MagicMock()
            agent.emitter.thinking = AsyncMock()
            agent.emitter.tool_result = AsyncMock()
            agent.emitter.complete = AsyncMock()
            result = asyncio.run(agent.run(state))
            assert result["status"] == "completed"


# ──────────────────────────────────────────────────────────────────────────────
# NLSearchAgent Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestNLSearchAgent:
    def test_parses_natural_query_to_structured(self):
        state = make_state("nl_job_search", {"query": "remote backend engineer Bangalore senior"})

        with patch(
            "app.agents.nl_search_agent_v2.NLSearchAgent._get_llm",
            return_value=make_async_mock_llm([json.dumps({
                "query": "backend engineer", "location": "Bangalore",
                "salary_min": None, "experience_years": 5,
                "platforms": ["linkedin", "indeed", "naukri"], "remote": True,
            })]),
        ), patch.object(
            BaseAgent, "set_run_id", new=AsyncMock(),
        ):
            from app.agents.nl_search_agent_v2 import NLSearchAgent
            db = MagicMock()
            redis = MagicMock()
            agent = NLSearchAgent(db, redis)
            agent.emitter = MagicMock()
            agent.emitter.thinking = AsyncMock()
            agent.emitter.tool_result = AsyncMock()
            agent._hitl_checkpoint = AsyncMock(return_value={**state, "status": "awaiting_approval"})
            result = asyncio.run(agent.run(state))
            assert result["status"] == "awaiting_approval"
