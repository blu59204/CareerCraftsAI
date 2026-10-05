"""Career Copilot chat orchestrator + gateway tool sessions.

The chat copilot is orchestration-only: it may start whitelisted runs and
read status for the authenticated user, but there is deliberately no tool
that can approve, cancel, or send anything — HITL stays a browser action.
"""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.core.request_context import current_user_id, reset_current_user_id, set_current_user_id

USER_ID = "user_test_1"
OTHER_ID = "user_other"


@pytest.fixture
def as_user():
    token = set_current_user_id(USER_ID)
    yield USER_ID
    reset_current_user_id(token)


@pytest.fixture
def as_other():
    token = set_current_user_id(OTHER_ID)
    yield OTHER_ID
    reset_current_user_id(token)


# ── Tool surface ─────────────────────────────────────────────────


def test_chat_tools_cannot_approve_cancel_or_send():
    from app.agents.chat_orchestrator import TOOLS

    names = {t.name for t in TOOLS}
    assert names == {
        "start_agent_run",
        "get_run_status",
        "list_recent_runs",
        "list_applications",
        "search_jobs_now",
    }
    assert not any(word in name for name in names for word in ("approve", "cancel", "send", "submit"))


def test_task_whitelist_excludes_direct_execution_paths():
    from app.agents.chat_orchestrator import ALLOWED_TASK_TYPES

    assert "job_search" in ALLOWED_TASK_TYPES and "auto_apply" in ALLOWED_TASK_TYPES
    assert "follow_up" not in ALLOWED_TASK_TYPES


# ── start_agent_run ──────────────────────────────────────────────


async def test_start_agent_run_rejects_non_whitelisted_task_type(as_user):
    from app.agents.chat_orchestrator import start_agent_run

    result = json.loads(
        await start_agent_run.ainvoke({"task_type": "nuke_database", "context": {}})
    )
    assert "not allowed" in result["error"]
    assert "nuke_database" not in result.get("allowed", [])


async def test_start_agent_run_happy_path_queues_and_returns_run_id(as_user, monkeypatch):
    from app.agents import chat_orchestrator as co

    captured = {}

    async def fake_queue(db, user, task_type, context):
        captured["task_type"] = task_type
        captured["context"] = context
        return "run-123"

    monkeypatch.setattr(co, "_get_user", AsyncMock(return_value=MagicMock(id="u1")))
    monkeypatch.setattr("app.api.v1.run_utils.queue_agent_run", fake_queue)
    monkeypatch.setattr(
        "app.core.database.AsyncSessionLocal",
        _fake_session_factory(MagicMock()),
    )

    result = json.loads(
        await co.start_agent_run.ainvoke(
            {"task_type": "job_search", "context": {"query": "python"}}
        )
    )
    assert result["run_id"] == "run-123"
    assert result["status"] == "queued"
    assert captured["task_type"] == "job_search"


async def test_start_agent_run_surfaces_concurrency_429(as_user, monkeypatch):
    from fastapi import HTTPException

    from app.agents import chat_orchestrator as co

    async def fake_queue(db, user, task_type, context):
        raise HTTPException(status_code=429, detail="Max 2 concurrent agent runs reached.")

    monkeypatch.setattr(co, "_get_user", AsyncMock(return_value=MagicMock(id="u1")))
    monkeypatch.setattr("app.api.v1.run_utils.queue_agent_run", fake_queue)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", _fake_session_factory(MagicMock()))

    result = json.loads(
        await co.start_agent_run.ainvoke({"task_type": "job_search", "context": {}})
    )
    assert "concurrent" in result["error"]


class _FakeSession:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *exc):
        return False


def _fake_session_factory(db):
    return lambda: _FakeSession(db)


# ── get_run_status ───────────────────────────────────────────────


async def test_get_run_status_scopes_to_owner_only(as_user, monkeypatch):
    """A run belonging to another user is indistinguishable from missing."""
    from app.agents import chat_orchestrator as co

    db = MagicMock()
    execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None)))
    db.execute = execute
    monkeypatch.setattr(co, "_get_user", AsyncMock(return_value=MagicMock(id="owner")))
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", _fake_session_factory(db))

    result = json.loads(await co.get_run_status.ainvoke({"run_id": str(uuid.uuid4())}))
    assert result == {"error": "Run not found."}


async def test_get_run_status_reports_pending_action_for_awaiting_approval(as_user, monkeypatch):
    from app.agents import chat_orchestrator as co

    run = SimpleNamespace(
        id=uuid.uuid4(),
        agent_type="auto_apply",
        status="awaiting_approval",
        output={"action_type": "auto_apply_approval", "details": "x" * 5000},
    )
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: run))
    )
    monkeypatch.setattr(co, "_get_user", AsyncMock(return_value=MagicMock(id="owner")))
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", _fake_session_factory(db))

    result = json.loads(await co.get_run_status.ainvoke({"run_id": str(run.id)}))
    assert result["status"] == "awaiting_approval"
    assert result["pending_action"]["action_type"] == "auto_apply_approval"
    assert result["pending_action"]["summary"].endswith("…[truncated]")
    assert len(result["pending_action"]["summary"]) <= 412  # 400 + marker


async def test_get_run_status_never_leaks_failed_run_error_detail(as_user, monkeypatch):
    from app.agents import chat_orchestrator as co

    run = SimpleNamespace(
        id=uuid.uuid4(),
        agent_type="resume_optimize",
        status="failed",
        output={"error": "stack trace with provider key hints"},
    )
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: run))
    )
    monkeypatch.setattr(co, "_get_user", AsyncMock(return_value=MagicMock(id="owner")))
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", _fake_session_factory(db))

    result = json.loads(await co.get_run_status.ainvoke({"run_id": str(run.id)}))
    assert result["error"] == "Agent failed"
    assert "provider" not in json.dumps(result)


async def test_get_run_status_rejects_non_uuid(as_user):
    from app.agents.chat_orchestrator import get_run_status

    result = json.loads(await get_run_status.ainvoke({"run_id": "../etc/passwd"}))
    assert "UUID" in result["error"]


# ── Graph node behavior ──────────────────────────────────────────


async def test_agent_node_answers_unauthenticated_without_user_context():
    from app.agents.chat_orchestrator import UNAUTHENTICATED_REPLY, agent_node

    state = {"messages": [HumanMessage(content="hi")]}
    result = await agent_node(state)
    assert result["messages"][0].content == UNAUTHENTICATED_REPLY


async def test_agent_node_reports_missing_model_configuration(as_user, monkeypatch):
    from fastapi import HTTPException

    from app.agents import chat_orchestrator as co

    async def fake_llm(user_id, db):
        raise HTTPException(status_code=400, detail="No active model configured.")

    monkeypatch.setattr("app.core.llm_gateway.get_chat_gateway_llm", fake_llm)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", _fake_session_factory(MagicMock()))

    result = await co.agent_node({"messages": [HumanMessage(content="hi")]})
    assert "No active model" in result["messages"][0].content


def test_chat_graph_compiles_with_checkpointer():
    from app.agents.chat_orchestrator import chat_graph

    assert chat_graph.checkpointer is not None


# ── Gateway tool sessions ────────────────────────────────────────


def test_gateway_rejects_tools_without_allow_tools_session():
    from app.core.llm_gateway import _validate_tools

    assert _validate_tools(None) is None
    with pytest.raises(ValueError):
        _validate_tools("not-a-list")
    with pytest.raises(ValueError):
        _validate_tools([{"type": "code_interpreter"}])
    with pytest.raises(ValueError):
        _validate_tools([{"type": "function", "function": {"name": "bad name!", "parameters": {}}}])
    too_big = [
        {"type": "function", "function": {"name": f"t{i}", "parameters": {}}} for i in range(33)
    ]
    with pytest.raises(ValueError):
        _validate_tools(too_big)


def test_gateway_validates_and_normalizes_valid_tools():
    from app.core.llm_gateway import _validate_tools

    cleaned = _validate_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "start_agent_run",
                    "description": "Start a run",
                    "parameters": {"type": "object", "properties": {}},
                    "sneaky_extra": True,
                },
            }
        ]
    )
    assert cleaned[0]["function"]["name"] == "start_agent_run"
    assert "sneaky_extra" not in cleaned[0]["function"]


def test_gateway_message_validation_is_stricter_without_tools():
    from app.core.llm_gateway import _validated_messages

    plain = [{"role": "user", "content": "hi"}]
    assert len(_validated_messages(plain, allow_tools=False)) == 1

    tool_turn = [{"role": "tool", "content": "42", "tool_call_id": "call_1"}]
    with pytest.raises(ValueError):
        _validated_messages(tool_turn, allow_tools=False)
    assert len(_validated_messages(tool_turn, allow_tools=True)) == 1

    assistant_null = [{"role": "assistant", "content": None}]
    with pytest.raises(ValueError):
        _validated_messages(assistant_null, allow_tools=False)
    with pytest.raises(ValueError):
        _validated_messages(assistant_null, allow_tools=True)  # null content needs tool_calls


def test_gateway_message_validation_bounds_tool_calls():
    from app.core.llm_gateway import _validated_messages

    huge_args = [{"role": "assistant", "content": None, "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "ok", "arguments": "x" * 21000}}
    ]}]
    with pytest.raises(ValueError):
        _validated_messages(huge_args, allow_tools=True)

    bad_id = [{"role": "assistant", "content": None, "tool_calls": [
        {"id": "", "type": "function", "function": {"name": "ok", "arguments": "{}"}}
    ]}]
    with pytest.raises(ValueError):
        _validated_messages(bad_id, allow_tools=True)


async def test_get_chat_gateway_llm_session_carries_allow_tools(monkeypatch):
    from app.core import llm_gateway as gw

    stored = {}
    client = AsyncMock()
    client.setex = AsyncMock(side_effect=lambda k, ttl, v: stored.update({k: json.loads(v)}))
    monkeypatch.setattr(gw, "_get_redis", lambda: client)

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(
                first=lambda: SimpleNamespace(
                    provider="anthropic",
                    model_name="claude-test",
                    api_key_enc="enc",
                    ollama_url=None,
                )
            )
        )
    )
    monkeypatch.setattr(
        "app.services.token_budget_service.check_budget", AsyncMock(return_value=100)
    )

    llm = await gw.get_chat_gateway_llm(USER_ID, db)
    (session,) = stored.values()
    assert session["allow_tools"] is True
    assert session["api_key_enc"] == "enc"
    assert "enc" not in (llm.openai_api_key.get_secret_value() or "")
    assert str(llm.openai_api_base).endswith("/llm-gateway/v1")
