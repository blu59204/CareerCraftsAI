import uuid

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
