"""Regression tests for Fix 5: HITL approval/SSE flow (2026-06-13 audit).

Every irreversible action (email send, job application submit) must be gated
behind an explicit user approval event.  These tests verify the gate cannot
be bypassed by:
  - Calling the approve endpoint on a run that isn't awaiting_approval
  - Missing the pending_action type check
  - Passing submit=True to apply_to_job (never happens — guard confirmed)
  - Calling fill_and_submit_form with submit=True from the auto-apply path

Bugs confirmed absent (audit P0):
  - apply_naukri previously returned status='applied' without HITL — fixed in Fix 2
  - apply_linkedin task string said "Click through all steps and Submit" — fixed in Fix 2
  - fill_and_submit_form is always called with submit=False from apply_to_any_portal
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. Email HITL gate: approve_and_send rejects non-awaiting_approval runs
# ---------------------------------------------------------------------------


def test_email_approve_rejects_completed_run():
    """approve_and_send must check run.status == 'awaiting_approval' before sending.

    Verifies the gate exists in source — prevents regression where a completed
    run could be re-approved and the email sent a second time.
    """
    import inspect
    from app.api.v1 import email as email_module

    source = inspect.getsource(email_module.approve_and_send)
    assert "awaiting_approval" in source, (
        "approve_and_send must check run.status == 'awaiting_approval' before sending"
    )
    # Must raise (400) when not awaiting_approval
    assert "raise HTTPException" in source
    assert "status_code=400" in source or "400" in source


def test_email_approve_rejects_wrong_action_type():
    """approve_and_send must check pending_action.type == 'send_email' before sending."""
    import inspect
    from app.api.v1 import email as email_module

    source = inspect.getsource(email_module.approve_and_send)
    assert "send_email" in source, (
        "approve_and_send must verify action type is 'send_email'"
    )
    assert "raise HTTPException" in source, (
        "approve_and_send must raise HTTPException when the pending action type is wrong"
    )


def test_email_approve_rejects_missing_run():
    """approve_and_send must return 404 when run is not found.

    Verifies the ownership + existence check in the source.
    """
    import inspect
    from app.api.v1 import email as email_module

    source = inspect.getsource(email_module.approve_and_send)
    assert "scalar_one_or_none" in source, "approve_and_send must query the run"
    assert "404" in source, "approve_and_send must raise 404 when run not found"
    assert "current_user.id" in source, "approve_and_send must filter by current_user.id"


# ---------------------------------------------------------------------------
# 2. Email agent always returns awaiting_approval, never sends directly
# ---------------------------------------------------------------------------


def test_email_agent_node_always_returns_awaiting_approval():
    """email_agent_node must return awaiting_approval — never 'completed' with a send.

    If the agent returned 'completed' and sent the email directly, the HITL gate
    in approve_and_send would never be reached.
    """
    from app.agents.email_agent import email_agent_node
    from app.agents.state import AgentState

    state: AgentState = {
        "user_id": "usr_test",
        "run_id": str(uuid.uuid4()),
        "task_type": "email",
        "messages": [],
        "context": {
            "company": "Acme Corp",
            "role": "Python Engineer",
            "recipient_email": "recruiter@acme.com",
        },
        "status": "running",
        "pending_action": None,
        "result": None,
        "error": None,
    }

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content="Subject: Following up\n\nHi, I'm interested in the role."
    )

    with (
        patch("app.agents.email_agent.fetch_model_settings", return_value=MagicMock()),
        patch("app.agents.email_agent._build_llm", return_value=mock_llm),
        patch("app.agents.email_agent.GmailMCPClient") as mock_gmail_cls,
        patch("app.agents.email_agent.think_and_select", return_value="Think: personalize."),
    ):
        mock_gmail = MagicMock()
        mock_gmail.search_threads.return_value = []
        mock_gmail_cls.return_value = mock_gmail

        result = email_agent_node(state)

    assert result["status"] == "awaiting_approval", (
        f"email_agent_node returned status='{result['status']}' — expected 'awaiting_approval'. "
        "If 'completed', the agent sent the email without user review."
    )
    assert result.get("pending_action") is not None
    assert result["pending_action"].get("type") == "send_email"
    # Critical: the agent must NOT have called send_message
    mock_gmail.send_message.assert_not_called()


# ---------------------------------------------------------------------------
# 3. apply_to_any_portal always calls fill_and_submit_form with submit=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_to_any_portal_always_calls_submit_false():
    """apply_to_any_portal must NEVER pass submit=True to fill_and_submit_form.

    submit=True would cause the form filler to click the final Submit button,
    bypassing the HITL checkpoint entirely.
    """
    from app.services.auto_apply_service import apply_to_any_portal

    submit_values: list[bool] = []

    async def _capture_fill(*args, **kwargs):
        submit_values.append(kwargs.get("submit", False))
        return {"status": "ready_for_review", "message": "ok"}

    with (
        patch("app.services.form_filler_service.fill_and_submit_form", side_effect=_capture_fill),
        patch("app.services.auto_apply_service.emit"),
        patch("app.services.auto_apply_service._human_delay", new=AsyncMock()),
    ):
        await apply_to_any_portal(
            MagicMock(), "usr_test",
            "https://boards.greenhouse.io/company/jobs/123",
            run_id="r1",
        )

    assert len(submit_values) == 1
    assert submit_values[0] is False, (
        f"fill_and_submit_form was called with submit={submit_values[0]}. "
        "submit=True bypasses the HITL gate and submits the application immediately."
    )


# ---------------------------------------------------------------------------
# 4. browser_control_service.apply_to_job: submit=False is the default
# ---------------------------------------------------------------------------


def test_apply_to_job_default_submit_is_false():
    """apply_to_job in browser_control_service must default to submit=False.

    The submit=True path exists for post-approval submission only. Any call
    from the auto-apply pipeline without an explicit approval must use False.
    """
    import inspect
    from app.services.browser_control_service import apply_to_job

    sig = inspect.signature(apply_to_job)
    submit_param = sig.parameters.get("submit")
    assert submit_param is not None, "apply_to_job must have a 'submit' parameter"
    assert submit_param.default is False, (
        f"apply_to_job 'submit' param default is {submit_param.default!r}, expected False. "
        "A True default would submit all applications without approval."
    )


def test_no_caller_passes_submit_true_to_apply_to_job():
    """Verify no production code path calls apply_to_job with submit=True.

    This is a source-scan test: reads the actual call sites and asserts none
    pass submit=True.  If a future change adds a submit=True call outside
    an approved post-approval handler, this test will catch it.
    """
    from pathlib import Path

    backend = Path(__file__).parent.parent.parent / "app"
    suspicious: list[str] = []

    for py_file in backend.rglob("*.py"):
        # Skip the service file itself (definition) and tests
        if "browser_control_service" in py_file.name:
            continue
        content = py_file.read_text(encoding="utf-8", errors="replace")
        # Look for calls that explicitly pass submit=True
        if "apply_to_job(" in content and "submit=True" in content:
            # Check if they're in the same call (rough proximity check)
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if "apply_to_job(" in line and "submit=True" in line:
                    suspicious.append(f"{py_file}:{i+1}: {line.strip()}")

    assert not suspicious, (
        "Found call(s) to apply_to_job with submit=True outside an approved "
        "post-approval handler:\n" + "\n".join(suspicious)
    )


# ---------------------------------------------------------------------------
# 5. auto_apply_pipeline emits checkpoint before any action
# ---------------------------------------------------------------------------


def test_email_agent_node_source_contains_awaiting_approval():
    """Structural check: email_agent_node must contain 'awaiting_approval' in its return paths.

    The audit found one instance where an agent returned 'completed' and performed
    a send inline. This test prevents regression by inspecting the source.
    """
    import inspect
    from app.agents import email_agent

    source = inspect.getsource(email_agent.email_agent_node)
    assert "awaiting_approval" in source, (
        "email_agent_node must set status='awaiting_approval' before returning — "
        "never send email directly from the agent node."
    )
    # Confirm the agent does NOT call gmail.send_message
    assert "send_message" not in source, (
        "email_agent_node must NOT call gmail.send_message — sending must only "
        "happen via the approved approve_and_send endpoint."
    )


def test_auto_apply_pipeline_source_never_passes_submit_true():
    """auto_apply_pipeline must never call browser apply with submit=True."""
    import inspect
    from app.agents import auto_apply_pipeline

    source = inspect.getsource(auto_apply_pipeline)
    # The pipeline queues actions for approval — it must not submit directly
    assert "submit=True" not in source, (
        "auto_apply_pipeline contains 'submit=True' — this bypasses the HITL gate."
    )
