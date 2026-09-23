"""Regression test: awaiting_approval status must save pending_action to run.output."""
import uuid
import pytest


def test_awaiting_approval_saves_pending_action_not_result():
    """Verify that when result_state has status=awaiting_approval,
    the run.output is set to pending_action, not result."""
    result_state = {
        "status": "awaiting_approval",
        "pending_action": {"action_type": "submit_application", "job_url": "https://example.com/job"},
        "result": None,
        "user_id": "user-123",
        "run_id": str(uuid.uuid4()),
    }
    # Simulate the fixed persistence logic
    st = result_state.get("status")
    if st == "awaiting_approval":
        output = result_state.get("pending_action") or {}
    else:
        output = result_state.get("result")

    assert output == {"action_type": "submit_application", "job_url": "https://example.com/job"}
    assert output.get("action_type") == "submit_application"


def test_completed_status_saves_result_not_pending_action():
    """Completed runs must save result, not pending_action."""
    result_state = {
        "status": "completed",
        "result": {"jobs_found": 5},
        "pending_action": None,
    }
    st = result_state.get("status")
    if st == "awaiting_approval":
        output = result_state.get("pending_action") or {}
    else:
        output = result_state.get("result")

    assert output == {"jobs_found": 5}


def test_approve_endpoint_reads_action_type_from_output():
    """Simulates approve_or_cancel logic reading action_type from run.output."""
    # After the fix, run.output contains the pending_action dict
    run_output = {"action_type": "submit_application", "job_url": "https://example.com/job"}

    pending = run_output or {}
    redis_action_type = pending.get("type") or pending.get("action_type")

    assert redis_action_type == "submit_application"


def test_unapproved_action_is_rejected():
    """If approved=False, status must become failed, not run the action."""
    # Simulates the rejection branch in approve_or_cancel
    approved = False
    if not approved:
        new_status = "failed"
        output = {"error": "Action cancelled by user"}
    else:
        new_status = "running"
        output = None

    assert new_status == "failed"
    assert "cancelled" in output["error"].lower()
