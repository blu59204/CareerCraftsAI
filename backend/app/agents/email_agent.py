import logging

from langchain_core.messages import AIMessage

from app.agents._llm_json import call_llm_json
from app.agents.prompts.email_prompt import OUTPUT_SCHEMA, SYSTEM_PROMPT, build_user_prompt
from app.agents.state import AgentState
from app.agents.thinking import think_and_select
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings
from app.services.gmail_service import GmailMCPClient

logger = logging.getLogger(__name__)

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

        draft = call_llm_json(
            llm,
            SYSTEM_PROMPT,
            build_user_prompt({
                "company": company,
                "role": role,
                "recipient": recipient,
                "thread": thread_context,
                "purpose": thinking,
            }),
            OUTPUT_SCHEMA,
        )

        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": {
                "type": "send_email",
                "recipient": recipient,
                "subject": draft.subject,
                "body": draft.body,
                "thinking": draft.intent_detected,
            },
            "messages": state["messages"] + [
                AIMessage(content=f"Email draft ready for {recipient}. Review before sending.")
            ],
        }
    except Exception as exc:
        logger.exception("Email agent failed for user %s", state.get("user_id"))
        return {
            **state,
            "status": "failed",
            "error": f"Email drafting failed: {str(exc)[:200]}",
            "messages": state["messages"] + [
                AIMessage(content="Email drafting failed; no fabricated message was created.")
            ],
        }
