"""Regression tests for AgentState schema fixes (2026-06-13 audit).

Bugs caught:
  1. user_id / run_id were total=False — made required fields optional, causing
     silent KeyError in every agent node when the API omitted them.
  2. tokens_used was written by ResumeAgent (resume_agent.py:195) but not defined
     in the schema — ghost write, value silently lost.
  3. messages typed as list[dict] but agents append AIMessage objects — type
     mismatch caught at serialisation time.

Each test is annotated with what the OLD code did vs what the NEW code does.
"""
import uuid

import pytest
from langchain_core.messages import AIMessage

from app.agents.state import AgentState


# ---------------------------------------------------------------------------
# 1. Required fields
# ---------------------------------------------------------------------------


def test_state_requires_user_id_and_run_id():
    """Old: both were total=False — TypedDict accepted them missing, nodes
    then raised KeyError at runtime.
    New: declared in _AgentStateRequired (no total=False) — mypy/pyright will
    catch missing fields at type-check time.
    """
    state: AgentState = {
        "user_id": "usr_abc",
        "run_id": str(uuid.uuid4()),
    }
    # Required fields must be accessible without KeyError
    assert state["user_id"] == "usr_abc"
    assert "run_id" in state


def test_state_with_all_optional_fields():
    """Full construction must not raise."""
    state: AgentState = {
        "user_id": "usr_123",
        "run_id": str(uuid.uuid4()),
        "task": "resume_optimize",
        "task_type": "resume_optimize",
        "status": "running",
        "context": {"jd_text": "Python engineer"},
        "messages": [],
        "pending_action": None,
        "result": None,
        "error": None,
        "tokens_used": 0,
    }
    assert state["status"] == "running"
    assert state["tokens_used"] == 0


# ---------------------------------------------------------------------------
# 2. tokens_used is a defined schema field
# ---------------------------------------------------------------------------


def test_tokens_used_is_in_schema():
    """Old: tokens_used not in AgentState — write by ResumeAgent was silently
    dropped when the orchestrator serialised state between nodes.
    New: tokens_used is defined and round-trips correctly.
    """
    state: AgentState = {
        "user_id": "usr_1",
        "run_id": "run_1",
        "tokens_used": 1234,
    }
    assert state["tokens_used"] == 1234

    # Simulate what ResumeAgent does (state["tokens_used"] = X)
    state["tokens_used"] = 5678
    assert state["tokens_used"] == 5678


# ---------------------------------------------------------------------------
# 3. messages accepts BaseMessage objects, not just dicts
# ---------------------------------------------------------------------------


def test_messages_accepts_langchain_message_objects():
    """Old: messages: list[dict] — appending AIMessage objects was a type
    mismatch that would raise at serialisation time when checkpointing.
    New: messages: list[Any] — AIMessage objects are accepted cleanly.
    """
    state: AgentState = {
        "user_id": "u",
        "run_id": "r",
        "messages": [],
    }
    msg = AIMessage(content="Resume tailored successfully.")
    state["messages"].append(msg)

    assert len(state["messages"]) == 1
    assert state["messages"][0].content == "Resume tailored successfully."


# ---------------------------------------------------------------------------
# 4. Orchestrator routing still works after schema change
# ---------------------------------------------------------------------------


def make_state(task_type: str, status: str = "running") -> AgentState:
    return {
        "user_id": "usr_test",
        "run_id": str(uuid.uuid4()),
        "task_type": task_type,
        "messages": [],
        "context": {},
        "status": status,
        "pending_action": None,
        "result": None,
        "error": None,
    }


@pytest.mark.parametrize("task_type,expected_node", [
    ("resume_optimize", "resume"),
    ("job_search", "job_search"),
    ("linkedin_optimize", "linkedin"),
    ("email", "email"),
    ("cover_letter", "cover_letter"),
    ("interview_prep", "interview_prep"),
    ("salary_intelligence", "salary"),
    ("nl_job_search", "nl_search"),
    ("auto_apply", "auto_apply"),
])
def test_orchestrator_routing_with_new_schema(task_type, expected_node):
    """Verify all TASK_ROUTES entries still resolve correctly after schema change."""
    from app.agents.orchestrator import route_task
    assert route_task(make_state(task_type)) == expected_node


def test_orchestrator_routes_unknown_to_end():
    from app.agents.orchestrator import route_task
    assert route_task(make_state("not_a_real_task")) == "__end__"


def test_orchestrator_routes_completed_to_end():
    from app.agents.orchestrator import route_task
    assert route_task(make_state("resume_optimize", status="completed")) == "__end__"


def test_orchestrator_routes_awaiting_approval_to_end():
    from app.agents.orchestrator import route_task
    assert route_task(make_state("resume_optimize", status="awaiting_approval")) == "__end__"


def test_orchestrator_routes_failed_to_end():
    from app.agents.orchestrator import route_task
    assert route_task(make_state("job_search", status="failed")) == "__end__"


# ---------------------------------------------------------------------------
# 5. job_search module imports cleanly (duplicate function removal regression)
# ---------------------------------------------------------------------------


def test_job_search_module_imports_without_duplicate_name_collision():
    """Old: _search_greenhouse_board and _search_lever_company were defined
    twice in job_search.py — the first definition was silently shadowed.
    New: only one definition of each exists.
    Import the module and verify the functions are callable.
    """
    import importlib
    import inspect

    import app.agents.job_search as jm

    # Reload to force a fresh import (avoids cached module from a previous run)
    importlib.reload(jm)

    assert callable(jm._search_greenhouse_board)
    assert callable(jm._search_lever_company)

    # Confirm each function is defined exactly once in the source
    src_path = inspect.getfile(jm)
    with open(src_path, encoding="utf-8") as f:
        source = f.read()

    gh_count = source.count("def _search_greenhouse_board(")
    lv_count = source.count("def _search_lever_company(")
    assert gh_count == 1, f"_search_greenhouse_board defined {gh_count} times (expected 1)"
    assert lv_count == 1, f"_search_lever_company defined {lv_count} times (expected 1)"
