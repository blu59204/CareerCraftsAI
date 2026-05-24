import uuid

import pytest
from langchain_core.messages import HumanMessage
from unittest.mock import MagicMock, patch

from app.agents.state import AgentState


def make_state() -> AgentState:
    return AgentState(
        user_id="usr_test123",
        run_id=str(uuid.uuid4()),
        task_type="email",
        messages=[HumanMessage(content="Draft follow-up for Stripe")],
        context={
            "company": "Stripe",
            "role": "Senior Python Engineer",
            "recipient_email": "recruiter@stripe.com",
            "application_id": str(uuid.uuid4()),
        },
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def test_email_agent_drafts_and_pauses_for_approval(mock_llm):
    from app.agents.email_agent import email_agent_node

    mock_llm.responses = [
        "Subject: Following up — Senior Python Engineer\n\nDear Hiring Team,\n\nI wanted to follow up..."
    ]

    with patch("app.agents.email_agent._get_model_settings", return_value=MagicMock(provider="openai")), \
         patch("app.agents.email_agent._build_llm", return_value=mock_llm), \
         patch("app.agents.email_agent.GmailMCPClient") as mock_gmail_cls:
        mock_gmail = MagicMock()
        mock_gmail.search_threads.return_value = []
        mock_gmail_cls.return_value = mock_gmail
        result = email_agent_node(make_state())

    assert result["status"] == "awaiting_approval"
    assert result["pending_action"]["type"] == "send_email"
    assert "subject" in result["pending_action"]
    assert "body" in result["pending_action"]
    assert result["pending_action"]["recipient"] == "recruiter@stripe.com"


def test_email_agent_never_auto_sends(mock_llm):
    """Critical: email agent must NEVER call send_message directly."""
    from app.agents.email_agent import email_agent_node

    mock_llm.responses = ["Subject: Test\n\nBody"]

    with patch("app.agents.email_agent._get_model_settings", return_value=MagicMock(provider="openai")), \
         patch("app.agents.email_agent._build_llm", return_value=mock_llm), \
         patch("app.agents.email_agent.GmailMCPClient") as mock_gmail_cls:
        mock_gmail = MagicMock()
        mock_gmail_cls.return_value = mock_gmail
        email_agent_node(make_state())

    mock_gmail.send_message.assert_not_called()


def test_email_agent_fails_gracefully():
    from app.agents.email_agent import email_agent_node

    with patch("app.agents.email_agent._get_model_settings", return_value=MagicMock()), \
         patch("app.agents.email_agent._build_llm", side_effect=Exception("LLM unavailable")):
        result = email_agent_node(make_state())

    assert result["status"] == "failed"
    assert "LLM unavailable" in result["error"]
