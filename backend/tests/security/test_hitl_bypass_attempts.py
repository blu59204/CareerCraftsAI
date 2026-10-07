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
                "company": "C",
                "role": "SWE",
                "recipient_email": "r@c.com",
            },
            messages=[],
            status="running",
            pending_action=None,
            result=None,
            error=None,
        )
        fake_llm = MagicMock()
        # The agent parses a JSON EmailOutput; a plain-text reply would make the
        # draft fail before the HITL gate is ever exercised.
        fake_llm.invoke = MagicMock(
            return_value=MagicMock(
                content=(
                    '{"subject": "Following up", "body": "Dear R, I want to apply.", '
                    '"intent_detected": "follow_up"}'
                )
            )
        )

        # NOTE: email_agent binds these names at module top, so patch the
        # agent module namespace — patching app.core.sync_db.* would miss and
        # hit the real DB (hang). Same rule applies to every agent test.
        with (
            patch(
                "app.agents.email_agent.fetch_model_settings",
                return_value=MagicMock(),
            ),
            patch(
                "app.agents.email_agent.GmailMCPClient",
                autospec=True,
            ) as MockGmail,
            patch(
                "app.agents.email_agent.build_agent_llm",
                return_value=fake_llm,
            ),
            patch(
                "app.agents.email_agent.think_and_select",
                return_value="hook",
            ),
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
            company="Acme",
            title="Python Engineer",
            job_url="https://example.com/j/123",
            platform="indeed",
            description="Python role building reliable software",
        )
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        emitted = []
        with (
            patch(
                "app.agents.auto_apply_pipeline.scrape_jobs",
                return_value=[job],
            ),
            patch(
                "app.agents.auto_apply_pipeline.fetch_model_settings",
                return_value=MagicMock(),
            ),
            patch(
                "app.agents.auto_apply_pipeline.fetch_user_profile_text",
                return_value="Senior Python dev",
            ),
            patch(
                "app.agents.auto_apply_pipeline.build_agent_llm",
                return_value=MagicMock(),
            ),
            patch(
                "app.agents.auto_apply_pipeline._score_job_quick",
                return_value=90,
            ),
            patch(
                "app.agents.auto_apply_pipeline.find_recruiter_contact",
                new=AsyncMock(return_value=MagicMock(best=None)),
            ),
            patch(
                "app.agents.auto_apply_pipeline.resume_agent_node",
                return_value={"status": "completed", "result": {}},
            ),
            patch(
                "app.core.database.AsyncSessionLocal",
                MagicMock(return_value=mock_cm),
            ),
            patch(
                "app.agents.auto_apply_pipeline.emit",
                side_effect=lambda run_id, event_type, payload: emitted.append(
                    (event_type, payload)
                ),
            ),
        ):
            results = asyncio.run(
                run_auto_apply_pipeline(
                    user_id="00000000-0000-0000-0000-000000000001",
                    search_query="python",
                    run_id="00000000-0000-0000-0000-000000000002",
                )
            )

        assert results["emails_sent"] == 0
        assert results["applications_sent"] == 0
        checkpoints = [p for t, p in emitted if t == "checkpoint"]
        assert checkpoints, "pipeline must emit an approval checkpoint"
        assert checkpoints[0].get("type") == "review_application_draft"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status,action,expected", [
        ("awaiting_approval", "submit_application", 422),
        ("expired", "send_email", 400),
        ("completed", "send_email", 400),
    ])
    async def test_approval_rejects_wrong_action_and_closed_checkpoint(self, status, action, expected):
        import uuid
        from types import SimpleNamespace
        from fastapi import HTTPException, Request
        from app.api.v1.agents import ApproveRequest, approve_or_cancel

        run = SimpleNamespace(status=status, input={}, output={"type": "send_email"})
        db = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: run)),
            commit=AsyncMock(),
        )
        with patch("app.workflows.starters.signal_agent_decision", new=AsyncMock()) as signal:
            with pytest.raises(HTTPException) as rejected:
                await approve_or_cancel.__wrapped__(
                    str(uuid.uuid4()), ApproveRequest(approved=True, action_type=action),
                    Request({"type": "http"}), db, SimpleNamespace(id=uuid.uuid4()),
                )
            assert rejected.value.status_code == expected
            signal.assert_not_awaited()
            db.commit.assert_not_awaited()
