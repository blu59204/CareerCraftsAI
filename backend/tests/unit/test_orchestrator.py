import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.state import AgentState


def make_state(task_type: str, status: str = "running") -> AgentState:
    return AgentState(
        user_id="usr_test",
        run_id=str(uuid.uuid4()),
        task_type=task_type,
        messages=[],
        context={},
        status=status,
        pending_action=None,
        result=None,
        error=None,
    )


def test_route_resume_optimize():
    from app.agents.orchestrator import route_task

    assert route_task(make_state("resume_optimize")) == "resume"


def test_route_job_search():
    from app.agents.orchestrator import route_task

    assert route_task(make_state("job_search")) == "job_search"


def test_route_linkedin_optimize():
    from app.agents.orchestrator import route_task

    assert route_task(make_state("linkedin_optimize")) == "linkedin"


def test_route_email():
    from app.agents.orchestrator import route_task

    assert route_task(make_state("email")) == "email"


def test_route_unknown_goes_to_end():
    from app.agents.orchestrator import route_task

    assert route_task(make_state("unknown")) == "__end__"


def test_route_completed_goes_to_end():
    from app.agents.orchestrator import route_task

    assert route_task(make_state("resume_optimize", status="completed")) == "__end__"


def test_route_awaiting_approval_goes_to_end():
    from app.agents.orchestrator import route_task

    assert route_task(make_state("resume_optimize", status="awaiting_approval")) == "__end__"


@pytest.mark.asyncio
async def test_agent_exception_persists_failed_status():
    from app.agents.orchestrator import _run_agent_safely

    async def broken(_state):
        raise RuntimeError("provider unavailable")

    with patch("app.core.model_router.get_and_reset_tokens", return_value=0), \
         patch("app.core.agent_runs_repository.upsert_agent_run", new=AsyncMock()) as upsert:
        with pytest.raises(RuntimeError, match="provider unavailable"):
            await _run_agent_safely(broken, make_state("email"))

    assert upsert.await_args.kwargs["status"] == "failed"
