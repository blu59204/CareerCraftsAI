"""Regressions for owner boundaries and producer/consumer contracts."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError


def test_foreign_interview_is_rejected_before_model_or_write(monkeypatch):
    from app.agents import interview_coach_agent as agent

    model, write = MagicMock(), MagicMock()
    monkeypatch.setattr(agent, "fetch_model_settings", lambda _: object())
    read = MagicMock(return_value={"user_id": "victim", "questions": [{"question": "secret"}]})
    monkeypatch.setattr(agent, "_get_interview_session", read)
    monkeypatch.setattr(agent, "build_agent_llm", model)
    monkeypatch.setattr(agent, "_update_session_answer", write)
    state = {
        "user_id": "attacker",
        "run_id": "run",
        "context": {
            "session_id": "foreign",
            "answer_text": "word " * 12,
        },
    }
    assert agent.evaluate_answer_node(state)["status"] == "failed"
    read.assert_called_once_with("foreign", "attacker")
    model.assert_not_called()
    write.assert_not_called()


def test_interview_read_and_write_queries_require_owner_and_write_locks(monkeypatch):
    from app.agents import interview_coach_agent as agent

    db = MagicMock()
    db.__enter__.return_value = db
    db.execute.return_value.scalars.return_value.first.return_value = None
    monkeypatch.setattr(agent, "_get_sync_factory", lambda: lambda: db)
    session_id, owner = str(uuid.uuid4()), str(uuid.uuid4())
    agent._get_interview_session(session_id, owner)
    agent._update_session_answer(session_id, owner, 0, "answer", 70)
    for call in db.execute.call_args_list:
        statement = call.args[0]
        assert owner in statement.compile().params.values()
        assert "interview_sessions.user_id" in str(statement)
    assert db.execute.call_args.args[0]._for_update_arg is not None


def test_interview_evaluation_requires_prompt_fields():
    from app.agents.interview_coach_agent import _EVALUATE_ANSWER_PROMPT, InterviewEvaluationOutput

    result = InterviewEvaluationOutput(clarity=8, relevance=7, depth=6, feedback="Use examples")
    assert round((result.clarity + result.relevance + result.depth) / 30 * 100) == 70
    for field in ("clarity", "relevance", "depth", "feedback"):
        assert f'"{field}"' in _EVALUATE_ANSWER_PROMPT
    with pytest.raises(ValidationError):
        InterviewEvaluationOutput.model_validate({"score": 95, "tips": ["Good"]})


def test_cover_letter_uses_profile_when_rag_empty(monkeypatch):
    from app.agents import cover_letter_agent as agent

    monkeypatch.setattr(agent, "fetch_model_settings", lambda _: object())
    monkeypatch.setattr(agent, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.core.sync_db.fetch_user_profile_text", lambda _: "VERIFIED PROFILE SENTINEL"
    )
    monkeypatch.setattr(agent, "build_agent_llm", lambda _: object())
    monkeypatch.setattr("app.core.event_bus.emit", lambda *a, **k: None)
    captured = []

    def generate(llm, system, prompt, schema):
        captured.append(prompt)
        return schema(
            cover_letter_markdown="Draft",
            hook_used="Hook",
            requirements_addressed=[],
            word_count=1,
            tone="formal",
            alternative_openings=[],
        )

    monkeypatch.setattr(agent, "call_llm_json", generate)
    result = agent.cover_letter_node(
        {
            "user_id": "owner",
            "run_id": "run",
            "messages": [],
            "context": {"jd_text": "Python Engineer", "tone": "formal"},
        }
    )
    assert result["status"] == "awaiting_approval"
    assert "VERIFIED PROFILE SENTINEL" in captured[0]


def test_jobspy_country_is_derived_in_active_adapter(monkeypatch):
    from app.services import job_platforms_service as platforms
    from app.services import job_search_service as search

    scrape = MagicMock(return_value=[])
    monkeypatch.setattr(platforms, "scrape_jobs", scrape)
    for location, country in [("London, UK", "uk"), ("New York, USA", "usa"), ("India", "India")]:
        search._adapter_jobspy("Engineer", location, 10)
        assert scrape.call_args.kwargs["country"].lower() == country.lower()


@pytest.mark.asyncio
async def test_inbox_locks_application_rows_before_transitions(monkeypatch):
    from app.services import application_status_service as service

    db = MagicMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    db.execute = AsyncMock(return_value=MagicMock())
    db.execute.return_value.scalars.return_value.all.return_value = []
    db.commit = AsyncMock()
    monkeypatch.setattr(service, "AsyncSessionLocal", lambda: db)
    await service.apply_inbox_updates(str(uuid.uuid4()), [])
    statement = db.execute.await_args.args[0]
    assert statement._for_update_arg is not None
    assert "ORDER BY job_applications.id" in str(statement)


@pytest.mark.asyncio
async def test_company_embeddings_have_live_owner_metadata_and_run_off_loop(monkeypatch):
    from app.agents import company_research_agent as agent
    from app.services import rag_service

    store = MagicMock()
    owner_id = str(uuid.uuid4())
    owner_db = MagicMock()
    owner_db.__enter__.return_value = owner_db
    owner_db.execute.return_value.scalar_one_or_none.return_value = SimpleNamespace(
        deletion_scheduled_for=None
    )
    monkeypatch.setattr("app.core.sync_db._get_sync_factory", lambda: lambda: owner_db)
    monkeypatch.setattr(agent, "get_embedding_model", lambda _: object())
    monkeypatch.setattr(agent, "get_embedding_provider", lambda _: "openai")
    monkeypatch.setattr(agent, "get_vector_store", lambda *a, **k: store)
    monkeypatch.setattr(rag_service, "_ensure_hnsw_index", lambda: None)
    calls = []

    async def thread(fn, *args):
        calls.append(fn)
        return fn(*args)

    monkeypatch.setattr(agent.asyncio, "to_thread", thread)
    await agent.embed_company_intel(
        owner_id, agent.CompanyIntel(company_name="Acme"), object(), "intel-id"
    )
    docs = store.add_documents.call_args.args[0]
    assert docs and all(
        d.metadata["user_id"] == owner_id and d.metadata["company_intel_id"] == "intel-id"
        for d in docs
    )
    assert len(calls) == 1 and calls[0].__name__ == "store_chunks"
    assert owner_db.execute.call_args.args[0]._for_update_arg is not None
    owner_db.execute.return_value.scalar_one_or_none.return_value = None
    store.add_documents.reset_mock()
    with pytest.raises(ValueError, match="deletion"):
        await agent.embed_company_intel(
            owner_id, agent.CompanyIntel(company_name="Acme"), object(), "intel-id"
        )
    store.add_documents.assert_not_called()


def test_company_retrieval_scopes_live_company_record(monkeypatch):
    from app.services import rag_service as rag

    db = MagicMock()
    db.__enter__.return_value = db
    db.execute.return_value.all.return_value = []
    monkeypatch.setattr("app.core.sync_db._get_sync_factory", lambda: lambda: db)
    embeddings = SimpleNamespace(embed_query=lambda _: [0.0] * rag.EMBEDDING_DIMENSIONS["openai"])
    assert rag._search_live_documents("owner", "company", "openai", embeddings, "Acme", 3) == []
    sql, params = db.execute.call_args.args
    assert "FROM company_intel" in str(sql) and "company_intel_id" in str(sql)
    assert "d.user_id::text = :owner" in str(sql) and params["owner"] == "owner"
    assert "FROM user_documents" not in str(sql)
