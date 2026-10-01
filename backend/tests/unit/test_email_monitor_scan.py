"""The inbox scan: summaries, company extraction, dedupe and persistence."""

from unittest.mock import AsyncMock, MagicMock

from app.agents import email_monitor_agent as monitor


def _state():
    return {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "run_id": "",
        "task_type": "email_monitor",
        "context": {},
        "messages": [],
        "status": "running",
        "pending_action": None,
        "result": None,
        "error": None,
    }


def test_company_is_extracted_from_mixed_case_text():
    # The regex needs capitals; the old code lowercased the text first and
    # so always answered UNKNOWN.
    result = monitor._classify_notification(
        {
            "subject": "Interview invitation",
            "snippet": "We would like to invite you to interview at Acme Corp. Thanks",
            "from": "jobs@acme.com",
        },
        llm=MagicMock(),
    )
    assert result["category"] == "INTERVIEW"
    assert result["company"] == "Acme Corp"


def test_scan_skips_handled_mail_classifies_new_mail_and_records_changes(monkeypatch):
    gmail = MagicMock()
    gmail.search_threads.side_effect = [[{"id": "m1"}, {"id": "m2"}], [{"id": "m2"}], [], [], []]
    gmail.get_message_summary.return_value = {
        "id": "m2",
        "from": "Acme <jobs@acme.com>",
        "subject": "Interview invitation",
        "snippet": "We would like to schedule an interview at Acme.",
    }
    monkeypatch.setattr(monitor, "GmailMCPClient", lambda user_id: gmail)
    monkeypatch.setattr(monitor, "fetch_model_settings", lambda user_id: MagicMock())
    monkeypatch.setattr(monitor, "build_agent_llm", lambda settings: MagicMock())
    processed = AsyncMock(return_value={"m1"})  # m1 was acted on in an earlier scan
    monkeypatch.setattr(monitor, "processed_message_ids", processed)
    applied = AsyncMock(return_value=[{"company": "Acme", "to_status": "interview"}])
    monkeypatch.setattr(monitor, "apply_inbox_updates", applied)

    result = monitor.email_monitor_node(_state())

    assert result["status"] == "completed"
    gmail.get_message_summary.assert_called_once_with("m2")  # m1 skipped, m2 fetched once
    (user_id, updates), _ = applied.call_args
    assert [u["message_id"] for u in updates] == ["m2"]
    assert result["result"]["changes"] == [{"company": "Acme", "to_status": "interview"}]


def test_a_scan_with_nothing_new_makes_no_model_calls(monkeypatch):
    gmail = MagicMock()
    gmail.search_threads.return_value = [{"id": "m1"}]
    monkeypatch.setattr(monitor, "GmailMCPClient", lambda user_id: gmail)
    monkeypatch.setattr(monitor, "fetch_model_settings", lambda user_id: MagicMock())
    build = MagicMock()
    monkeypatch.setattr(monitor, "build_agent_llm", build)
    monkeypatch.setattr(monitor, "processed_message_ids", AsyncMock(return_value={"m1"}))

    result = monitor.email_monitor_node(_state())

    assert result["result"]["updates"] == []
    build.assert_not_called()
    gmail.get_message_summary.assert_not_called()
