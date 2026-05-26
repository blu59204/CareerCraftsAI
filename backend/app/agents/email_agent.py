import logging

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings
from app.services.gmail_service import GmailMCPClient

logger = logging.getLogger(__name__)

_OUTREACH_PROMPT = """You are writing a professional follow-up email for a job application.

Company: {company}
Role: {role}
Prior thread context: {thread_context}

Write a concise, professional email (3-4 short paragraphs max).
Format your response exactly as:
Subject: <subject line>

<email body>

Do NOT include placeholder text. Write a complete, ready-to-send email."""


def email_agent_node(state: AgentState) -> AgentState:
    try:
        user_id = state["user_id"]
        ctx = state["context"]
        company = ctx.get("company", "")
        role = ctx.get("role", "")
        recipient = ctx.get("recipient_email", "")

        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings configured for user")

        gmail = GmailMCPClient(user_id)
        threads = gmail.search_threads(
            f"from:{recipient} OR subject:{company}", max_results=3
        )
        thread_context = (
            "\n".join(str(t) for t in threads[:2]) if threads else "No prior threads found."
        )

        llm = _build_llm(model_settings)
        response = llm.invoke([HumanMessage(
            content=_OUTREACH_PROMPT.format(
                company=company, role=role, thread_context=thread_context
            )
        )])

        full_text = response.content.strip()
        subject = ""
        body = full_text
        if full_text.startswith("Subject:"):
            lines = full_text.split("\n", 2)
            subject = lines[0].replace("Subject:", "").strip()
            body = lines[2].strip() if len(lines) > 2 else ""

        # NEVER call gmail.send_message here — human gate enforced via /approve endpoint
        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": {
                "type": "send_email",
                "recipient": recipient,
                "subject": subject,
                "body": body,
            },
            "messages": state["messages"] + [
                AIMessage(content=f"Email draft ready for {recipient}. Review before sending.")
            ],
        }
    except Exception as exc:
        logger.error("Email agent failed for user %s: %s", state.get("user_id"), exc)
        return {**state, "status": "failed", "error": str(exc)}
