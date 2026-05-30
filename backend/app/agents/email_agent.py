import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.state import AgentState
from app.agents.thinking import think_and_select
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings
from app.services.gmail_service import GmailMCPClient

logger = logging.getLogger(__name__)

_OUTREACH_PROMPT = """You are writing a professional follow-up email for a job application.

Company: {company}
Role: {role}
Prior thread context: {thread_context}

STRATEGIC THINKING (follow this approach):
{thinking}

Write a concise, professional email (3-4 short paragraphs max).
Format your response exactly as:
Subject: <subject line>

<email body>

Do NOT include placeholder text. Write a complete, ready-to-send email."""


def _fallback_email(company: str, role: str, reason: str) -> tuple[str, str, str]:
    role_text = role or "the role"
    company_text = company or "your team"
    subject = f"Following up on {role_text}"
    body = (
        f"Hi,\n\n"
        f"I wanted to follow up on my interest in {role_text} at {company_text}. "
        "My background aligns with building reliable software, collaborating across teams, "
        "and moving product work from unclear requirements to shipped results.\n\n"
        "I would welcome the chance to share more context and learn what the team needs most right now.\n\n"
        "Best,\n"
    )
    thinking = f"Fallback draft used because live email/model context failed: {reason}"
    return subject, body, thinking


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

        try:
            gmail = GmailMCPClient(user_id)
            threads = gmail.search_threads(
                f"from:{recipient} OR subject:{company}", max_results=3
            )
        except Exception as exc:
            logger.warning("Email thread lookup failed for user %s: %s", user_id, exc)
            threads = []
        thread_context = (
            "\n".join(str(t) for t in threads[:2]) if threads else "No prior threads found."
        )

        llm = _build_llm(model_settings)

        # ── Think: What angle to take, what to emphasize ─────────────
        thinking = think_and_select(
            llm=llm,
            task_description=f"Write outreach email to {recipient} about {role} at {company}",
            user_context=f"Prior email threads: {thread_context}",
            target_context=f"Company: {company}, Role: {role}",
            selection_criteria="What hook will get a response? What's unique about this candidate for this role?",
        )

        response = llm.invoke([HumanMessage(
            content=_OUTREACH_PROMPT.format(
                company=company, role=role, thread_context=thread_context, thinking=thinking
            )
        )])

        full_text = response.content.strip()
        subject = ""
        body = full_text
        if full_text.startswith("Subject:"):
            lines = full_text.split("\n", 2)
            subject = lines[0].replace("Subject:", "").strip()
            body = lines[2].strip() if len(lines) > 2 else ""

        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": {
                "type": "send_email",
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "thinking": thinking,
            },
            "messages": state["messages"] + [
                AIMessage(content=f"Email draft ready for {recipient}. Review before sending.")
            ],
        }
    except Exception as exc:
        logger.error("Email agent failed for user %s: %s", state.get("user_id"), exc)
        ctx = state.get("context", {})
        company = ctx.get("company", "")
        role = ctx.get("role", "")
        recipient = ctx.get("recipient_email", "")
        subject, body, thinking = _fallback_email(company, role, "Email drafting failed")
        output = {
            "type": "send_email" if recipient else "email_draft",
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "thinking": thinking,
        }
        return {
            **state,
            "status": "awaiting_approval" if recipient else "completed",
            "pending_action": output if recipient else None,
            "result": None if recipient else output,
            "messages": state["messages"] + [
                AIMessage(content="Email fallback draft ready.")
            ],
        }
