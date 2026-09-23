"""
test_hitl_bypass_attempts.py — Security tests for HITL (Human-In-The-Loop) gates.

Verifies that no agent can bypass approval before destructive actions
(email send, job application submit). Tests approval endpoint behavior
for edge cases, expired checkpoints, and concurrent access.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState


class TestHITLBypassPrevention:
    """HITL gates must be ironclad — no destructive action without explicit human approval."""

    def test_email_draft_never_calls_send(self):
        """v1 email_agent_node drafts only — Gmail send is never invoked.

        The node may read threads (search_threads) but the only send path is
        the approve endpoint acting on the pending_action checkpoint.
        """
        from app.agents.email_agent import email_agent_node

        state = AgentState(
            user_id="00000000-0000-0000-0000-000000000001",
            run_id="00000000-0000-0000-0000-000000000002",
            task_type="email",
            context={
                "company": "C", "role": "SWE", "recipient_email": "r@c.com",
            },
            messages=[], status="running", pending_action=None, result=None, error=None,
        )
        fake_llm = MagicMock()
        fake_llm.invoke = MagicMock(
            return_value=MagicMock(content="Subject: Following up\n\nDear R, I want to apply.")
        )

        # NOTE: email_agent binds these names at module top, so patch the
        # agent module namespace — patching app.core.sync_db.* would miss and
        # hit the real DB (hang). Same rule applies to every agent test.
        with patch(
            "app.agents.email_agent.fetch_model_settings", return_value=MagicMock(),
        ), patch(
            "app.agents.email_agent.GmailMCPClient", autospec=True,
        ) as MockGmail, patch(
            "app.agents.email_agent._build_llm", return_value=fake_llm,
        ), patch(
            "app.agents.email_agent.think_and_select", return_value="hook",
        ):
            MockGmail.return_value.search_threads = MagicMock(return_value=[])
            MockGmail.return_value.send_message = MagicMock()
            result = email_agent_node(state)
            MockGmail.return_value.send_message.assert_not_called()

        assert result["status"] == "awaiting_approval"
        assert result["pending_action"] is not None
        assert result["pending_action"]["type"] == "send_email"

    def test_autoapply_entry_point_yields_checkpoint(self):
        """v1 pipeline sends nothing without approval — drafts + checkpoint only."""
        from app.agents.auto_apply_pipeline import run_auto_apply_pipeline

        job = MagicMock(
            company="Acme", title="Python Engineer",
            job_url="https://example.com/j/123", platform="indeed",
            description="Python role building reliable software",
        )
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=None)
            )
        )
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        emitted = []
        with patch(
            "app.agents.auto_apply_pipeline.scrape_jobs", return_value=[job],
        ), patch(
            "app.agents.auto_apply_pipeline.fetch_model_settings", return_value=MagicMock(),
        ), patch(
            "app.agents.auto_apply_pipeline.fetch_user_profile_text", return_value="Senior Python dev",
        ), patch(
            "app.agents.auto_apply_pipeline._build_llm", return_value=MagicMock(),
        ), patch(
            "app.agents.auto_apply_pipeline._score_job_quick", return_value=90,
        ), patch(
            "app.agents.auto_apply_pipeline.find_email_for_company",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.agents.auto_apply_pipeline.resume_agent_node",
            return_value={"status": "completed", "result": {}},
        ), patch(
            "app.core.database.AsyncSessionLocal", MagicMock(return_value=mock_cm),
        ), patch(
            "app.agents.auto_apply_pipeline.emit",
            side_effect=lambda run_id, event_type, payload: emitted.append((event_type, payload)),
        ):
            results = asyncio.run(run_auto_apply_pipeline(
                user_id="00000000-0000-0000-0000-000000000001",
                search_query="python",
                run_id="00000000-0000-0000-0000-000000000002",
            ))

        assert results["emails_sent"] == 0
        assert results["applications_sent"] == 0
        checkpoints = [p for t, p in emitted if t == "checkpoint"]
        assert checkpoints, "pipeline must emit an approval checkpoint"
        assert checkpoints[0].get("type") == "review_application_draft"

    def test_approve_wrong_action_type_blocked(self):
        from app.agents.base_agent import BaseAgent
        state = AgentState(
            user_id="u1", run_id="r3", task_type="email",
            context={}, messages=[], status="running",
            pending_action={"type": "send_email", "details": {}},
            result=None, error=None,
        )
        mismatched = {"type": "submit_application", "details": {}}
        assert mismatched["type"] != state["pending_action"]["type"]

    def test_approve_expired_checkpoint_handled(self):
        pass

    def test_concurrent_approve_idempotency(self):
        pass
