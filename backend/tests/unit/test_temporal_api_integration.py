"""API-layer Temporal integration: starting AutoApplyWorkflow from
prepare-apply, and routing approve/cancel through workflow signals for an
application run. The ownership/job-url/resume checks that run before are
covered by test_fixes_e2e.py's test_prepare_application_apply_* tests.
"""

import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.exceptions import WorkflowAlreadyStartedError


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["extension", "server_browser"])
async def test_start_temporal_auto_apply_starts_workflow_with_stable_id(monkeypatch, mode):
    from app.api.v1 import jobs as jobs_module
    from app.workflows.auto_apply import auto_apply_workflow_id

    user_id = uuid.uuid4()
    application_id = uuid.uuid4()

    fake_client = MagicMock()
    fake_client.start_workflow = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(
        "app.workflows.starters.get_temporal_client",
        AsyncMock(return_value=fake_client),
    )
    monkeypatch.setattr(jobs_module.settings, "APPLY_EXECUTION_MODE", mode)
    monkeypatch.setattr(jobs_module, "_await_temporal_run_id", AsyncMock(return_value="run-123"))

    result = await jobs_module._start_temporal_auto_apply(user_id, application_id)

    expected_id = auto_apply_workflow_id(str(user_id), str(application_id))
    fake_client.start_workflow.assert_awaited_once()
    intent = fake_client.start_workflow.call_args.args[1]
    call_kwargs = fake_client.start_workflow.call_args.kwargs
    assert call_kwargs["id"] == expected_id
    assert intent.mode == mode
    # The run id is chosen up front, so the response never carries the run
    # of a previous attempt for the same application.
    assert intent.run_id
    jobs_module._await_temporal_run_id.assert_awaited_once_with(
        user_id, application_id, intent.run_id
    )
    # The extension flow waits on a person and bounds itself with timers.
    assert call_kwargs["execution_timeout"] == (
        None
        if mode == "extension"
        else timedelta(seconds=jobs_module.settings.TEMPORAL_WORKFLOW_EXECUTION_TIMEOUT_S)
    )
    assert result == {
        "run_id": "run-123",
        "workflow_id": expected_id,
        "engine": "temporal",
        "mode": mode,
        "status": "queued",
    }


@pytest.mark.asyncio
async def test_start_temporal_auto_apply_reuses_existing_workflow_on_repeated_start(
    monkeypatch,
):
    """Required behavior: repeated start requests return the existing run
    instead of creating an orphan — Temporal itself enforces this via the
    stable workflow id; this test proves the API layer handles that
    rejection gracefully instead of raising a 500."""
    from app.api.v1 import jobs as jobs_module

    user_id = uuid.uuid4()
    application_id = uuid.uuid4()

    fake_client = MagicMock()
    fake_client.start_workflow = AsyncMock(
        side_effect=WorkflowAlreadyStartedError(
            workflow_id="wf-1",
            workflow_type="AutoApplyWorkflow",
        )
    )
    monkeypatch.setattr(
        "app.workflows.starters.get_temporal_client",
        AsyncMock(return_value=fake_client),
    )
    monkeypatch.setattr(
        jobs_module, "_await_temporal_run_id", AsyncMock(return_value="run-existing")
    )

    result = await jobs_module._start_temporal_auto_apply(user_id, application_id)

    assert result["status"] == "already_running"
    assert result["run_id"] == "run-existing"


@pytest.mark.asyncio
async def test_start_temporal_auto_apply_answers_503_when_temporal_is_down(monkeypatch):
    from fastapi import HTTPException

    from app.api.v1 import jobs as jobs_module

    monkeypatch.setattr(
        "app.workflows.starters.get_temporal_client",
        AsyncMock(side_effect=RuntimeError("connection refused")),
    )
    with pytest.raises(HTTPException) as exc_info:
        await jobs_module._start_temporal_auto_apply(uuid.uuid4(), uuid.uuid4())
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_approve_signals_temporal_workflow_for_browser_review():
    from app.api.v1.agents import _signal_temporal_approval
    from app.models.db import AgentRun
    from app.workflows.auto_apply import AutoApplyWorkflow

    run = AgentRun(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        agent_type="apply_prepare",
        status="awaiting_approval",
        input={"engine": "temporal", "workflow_id": "auto-apply/u1/j1"},
    )
    fake_handle = MagicMock()
    fake_handle.signal = AsyncMock()
    fake_client = MagicMock()
    fake_client.get_workflow_handle_for = MagicMock(return_value=fake_handle)

    import app.api.v1.agents as agents_module

    with patch(
        "app.workflows.starters.get_temporal_client",
        AsyncMock(return_value=fake_client),
    ):
        await agents_module._signal_temporal_approval(run, "browser_review", {})

    fake_client.get_workflow_handle_for.assert_called_once_with(
        AutoApplyWorkflow.run, workflow_id="auto-apply/u1/j1"
    )
    fake_handle.signal.assert_awaited_once_with(AutoApplyWorkflow.approve)


@pytest.mark.asyncio
async def test_approve_signals_answers_for_application_answers_required():
    from app.api.v1.agents import _signal_temporal_approval
    from app.models.db import AgentRun
    from app.workflows.auto_apply import AutoApplyWorkflow

    run = AgentRun(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        agent_type="apply_prepare",
        status="awaiting_approval",
        input={"engine": "temporal", "workflow_id": "auto-apply/u1/j1"},
    )
    fake_handle = MagicMock()
    fake_handle.signal = AsyncMock()
    fake_client = MagicMock()
    fake_client.get_workflow_handle_for = MagicMock(return_value=fake_handle)

    import app.api.v1.agents as agents_module

    with patch(
        "app.workflows.starters.get_temporal_client",
        AsyncMock(return_value=fake_client),
    ):
        await agents_module._signal_temporal_approval(
            run,
            "application_answers_required",
            {"answers": {"sponsor": "No"}},
        )

    fake_handle.signal.assert_awaited_once_with(
        AutoApplyWorkflow.provide_answers, {"sponsor": "No"}
    )


@pytest.mark.asyncio
async def test_approve_rejects_temporal_run_missing_workflow_id():
    from fastapi import HTTPException

    from app.api.v1.agents import _signal_temporal_approval
    from app.models.db import AgentRun

    run = AgentRun(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        agent_type="apply_prepare",
        status="awaiting_approval",
        input={"engine": "temporal"},
    )
    with pytest.raises(HTTPException) as exc_info:
        await _signal_temporal_approval(run, "browser_review", {})
    assert exc_info.value.status_code == 500
