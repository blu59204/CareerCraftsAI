"""Unit tests for the cover_letter agent pass.

The node speaks prompts/cover_letter_prompt exclusively (no inline prompt
text) and never touches the network: RAG, LLM build, and persistence are
all mocked. Cover letters are drafts for review — nothing is ever sent.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from app.agents.state import AgentState


def make_state(**ctx) -> AgentState:
    context = {"tone": "formal", "jd_text": "Backend Engineer building reliable APIs"}
    context.update(ctx)
    return AgentState(
        user_id="usr_test123",
        run_id=str(uuid.uuid4()),
        task_type="cover_letter",
        messages=[HumanMessage(content="write it")],
        context=context,
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def _valid_cover_json() -> str:
    return json.dumps({
        "cover_letter_markdown": "Dear Hiring Manager,\n\nI build reliable APIs.",
        "hook_used": "API reliability hook",
        "requirements_addressed": ["Python", "APIs"],
        "word_count": 42,
        "tone": "formal",
        "alternative_openings": ["Alt opener one.", "Alt opener two."],
    })


def _patches(mock_llm, **overrides):
    from app.agents import cover_letter_agent as cla

    mock_llm.responses = [_valid_cover_json()]
    kw = dict(
        fetch_model_settings=MagicMock(provider="openai"),
        retrieve=[MagicMock(page_content="5 years Python experience")],
        _build_llm=mock_llm,
        emit=None,
    )
    kw.update(overrides)
    return [
        patch.object(cla, "fetch_model_settings", return_value=kw["fetch_model_settings"]),
        patch.object(cla, "retrieve", return_value=kw["retrieve"]),
        patch.object(cla, "_build_llm", return_value=kw["_build_llm"]),
        patch("app.core.event_bus.emit"),
    ]


def test_cover_letter_returns_schema_draft_for_review(mock_llm):
    from app.agents import cover_letter_agent as cla

    patches = _patches(mock_llm)
    with patches[0], patches[1], patches[2], patches[3]:
        result = cla.cover_letter_node(make_state())

    assert result["status"] == "awaiting_approval"
    pending = result["pending_action"]
    assert pending["type"] == "cover_letter_review"
    assert pending["cover_letter_markdown"].startswith("Dear Hiring Manager")
    assert pending["hook_used"] == "API reliability hook"
    assert pending["requirements_addressed"] == ["Python", "APIs"]
    assert pending["tone"] == "formal"
    assert len(pending["alternative_openings"]) == 2
    assert pending["document_id"] is None  # ad-hoc: no application, no persist


def test_cover_letter_persists_version_when_application_given(mock_llm):
    from app.agents import cover_letter_agent as cla

    patches = _patches(mock_llm)
    with patches[0], patches[1], patches[2], patches[3]:
        with patch.object(
            cla, "_store_cover_letter", return_value={"document_id": "doc-1", "version_number": 3}
        ) as store:
            result = cla.cover_letter_node(
                make_state(job_application_id="00000000-0000-0000-0000-000000000009")
            )
    store.assert_called_once()
    assert result["pending_action"]["document_id"] == "doc-1"
    assert result["pending_action"]["version_number"] == 3


def test_cover_letter_accepts_legacy_application_id_key(mock_llm):
    from app.agents import cover_letter_agent as cla

    patches = _patches(mock_llm)
    with patches[0], patches[1], patches[2], patches[3]:
        with patch.object(
            cla, "_store_cover_letter", return_value={"document_id": "doc-9", "version_number": 1}
        ) as store:
            cla.cover_letter_node(
                make_state(application_id="00000000-0000-0000-0000-000000000009")
            )
    store.assert_called_once()


def test_cover_letter_degrades_when_persist_fails(mock_llm):
    from app.agents import cover_letter_agent as cla

    patches = _patches(mock_llm)
    with patches[0], patches[1], patches[2], patches[3]:
        with patch.object(cla, "_store_cover_letter", side_effect=Exception("db down")):
            result = cla.cover_letter_node(
                make_state(job_application_id="00000000-0000-0000-0000-000000000009")
            )
    assert result["status"] == "awaiting_approval"
    assert result["pending_action"]["document_id"] is None
    assert "cover_letter_markdown" in result["pending_action"]
    assert "persist_warning" in result["pending_action"]


def test_cover_letter_unknown_application_fails_loudly(mock_llm):
    from app.agents import cover_letter_agent as cla

    patches = _patches(mock_llm)
    with patches[0], patches[1], patches[2], patches[3]:
        with patch.object(
            cla, "_store_cover_letter", side_effect=ValueError("Job application not found")
        ):
            result = cla.cover_letter_node(
                make_state(job_application_id="00000000-0000-0000-0000-000000000009")
            )
    # Not a silent draft: explicit failure so the client can tell it apart
    # from ad-hoc success. No victim data is exposed.
    assert result["status"] == "failed"


def test_cover_letter_missing_jd_is_error():
    from app.agents import cover_letter_agent as cla

    result = cla.cover_letter_node(make_state(jd_text="  "))
    assert result["status"] == "failed"
    assert "jd_text" in result["error"]


def test_cover_letter_invalid_tone_is_error():
    from app.agents import cover_letter_agent as cla

    result = cla.cover_letter_node(make_state(tone="shakespearean"))
    assert result["status"] == "failed"
    assert "tone" in result["error"]


def test_cover_letter_no_model_settings_is_error():
    from app.agents import cover_letter_agent as cla

    with patch.object(cla, "fetch_model_settings", return_value=None):
        result = cla.cover_letter_node(make_state())
    assert result["status"] == "failed"
    assert "model" in result["error"]
