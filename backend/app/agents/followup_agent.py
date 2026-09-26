import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


async def schedule_followups(
    user_id: str, application_id: str, applied_at: datetime | None
) -> None:
    """Schedule the day-5 and day-12 follow-up drafts, keyed off applied_at.

    Runs as a Temporal FollowupWorkflow whose id is derived from the
    application, so repeated calls (a retried activity, marking the same
    application applied twice) never schedule a second set of drafts.
    """
    from app.workflows.starters import start_followups

    started = await start_followups(user_id, application_id, applied_at or datetime.now(UTC))
    if started:
        logger.info("Scheduled day-5/day-12 follow-ups for application %s", application_id)
    else:
        logger.debug("Follow-ups already scheduled for application %s", application_id)


def _fallback_followup_draft(company: str, role: str, stage: str) -> dict:
    company_text = company or "the team"
    role_text = role or "the role"
    nudge = "wanted to briefly follow up" if stage == "day5" else "wanted to check in one last time"
    subject = f"Following up: {role_text} at {company_text}"
    body = (
        f"Hi,\n\nI {nudge} on my application for {role_text} at {company_text}. "
        "I remain very interested and would welcome any update on next steps.\n\n"
        "Thanks for your time,\n"
    )
    return {"subject": subject, "body": body}


def build_followup_draft(
    user_id: str,
    company: str,
    role: str,
    applied_at: datetime | None,
    day: int,
) -> dict:
    """Draft a day-5/day-12 follow-up email. DRAFT ONLY — the caller
    (internal.py::run_followup) must route this through a human approval
    checkpoint before anything is sent; this function never sends email.
    """
    stage = "day5" if day <= 5 else "day12"
    try:
        from app.agents._llm_json import call_llm_json
        from app.agents.prompts.followup_prompt import OUTPUT_SCHEMA as FollowupOutput
        from app.agents.prompts.followup_prompt import SYSTEM_PROMPT as FOLLOWUP_SYSTEM_PROMPT
        from app.agents.prompts.followup_prompt import build_user_prompt as build_followup_prompt
        from app.core.model_router import _build_llm
        from app.core.sync_db import fetch_model_settings

        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            raise ValueError("no active model settings for user")
        llm = _build_llm(model_settings)
        parsed = call_llm_json(
            llm,
            FOLLOWUP_SYSTEM_PROMPT,
            build_followup_prompt(
                {
                    "role": role or "NOT_PROVIDED",
                    "company": company or "NOT_PROVIDED",
                    "applied_on": applied_at.date().isoformat() if applied_at else "NOT_PROVIDED",
                    "followup_stage": stage,
                }
            ),
            FollowupOutput,
        )
        return {"subject": parsed.subject, "body": parsed.body}
    except Exception as exc:
        logger.warning("Follow-up draft LLM failed for user %s, using template: %s", user_id, exc)
        return _fallback_followup_draft(company, role, stage)
