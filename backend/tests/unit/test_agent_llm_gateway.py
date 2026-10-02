"""Agent nodes reach their model only through the internal gateway."""

import json
import re
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

AGENTS = Path(__file__).resolve().parents[2] / "app" / "agents"


def test_agents_never_build_a_keyed_llm():
    offenders = [
        path.name
        for path in AGENTS.rglob("*.py")
        if re.search(r"\b_build_llm\b|\b_make_llm\b", path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_agent_llm_carries_a_session_token_not_the_key(monkeypatch):
    from app.core import model_router

    stored = {}
    client = MagicMock()
    client.__enter__.return_value = client
    client.setex.side_effect = lambda key, ttl, value: stored.update({key: json.loads(value)})
    monkeypatch.setattr("app.core.model_router._check_budget_sync", lambda user_id: None)
    user_id = uuid.uuid4()
    model_settings = SimpleNamespace(
        user_id=user_id,
        provider="anthropic",
        model_name="claude-test",
        api_key_enc="encrypted-real-key",
        ollama_url=None,
    )

    with patch("redis.from_url", return_value=client):
        llm = model_router.build_agent_llm(model_settings)

    token = llm.openai_api_key.get_secret_value()
    assert "encrypted-real-key" not in token
    assert str(llm.openai_api_base).endswith("/llm-gateway/v1")
    (session,) = stored.values()
    assert session["user_id"] == str(user_id)
    assert session["api_key_enc"] == "encrypted-real-key"  # only the gateway sees it


def test_agent_llm_requires_a_member():
    from app.core import model_router

    with pytest.raises(ValueError, match="user_id"):
        model_router.build_agent_llm(SimpleNamespace(provider="openai", model_name="m"))


def test_security_rules_are_merged_into_the_system_prompt_once():
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.agents.prompts import _COMMON, SECURITY_RULES, with_security_rules

    bare = with_security_rules([HumanMessage(content="Classify this email")])
    assert [type(m) for m in bare] == [SystemMessage, HumanMessage]
    assert bare[0].content == SECURITY_RULES

    merged = with_security_rules([SystemMessage(content="Score this job."), HumanMessage("x")])
    assert len(merged) == 2
    assert merged[0].content == f"{SECURITY_RULES}\n\nScore this job."

    already = [SystemMessage(content=_COMMON), HumanMessage("x")]
    assert with_security_rules(already) == already
