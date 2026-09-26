"""Agent execution and approval continuations.

Temporal (app/workflows/) decides *when* these run and guarantees they run;
this module is *what* runs. PostgreSQL stays the user-facing record of each
run. External writes are never automatically replayed after an uncertain
outcome — the workflows run every continuation at most once.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.db import AgentRun, ApplicationAttempt

# ApplicationAttempt states that block starting a new attempt for the same
# (user, job_application) — see docs on Task 2 idempotent submission.
ACTIVE_SUBMISSION_STATES = {"submitting", "submitted", "verified"}

DRAFT_TYPES = {
    "resume_ready",
    "cover_letter_review",
    "linkedin_edits",
    "interview_prep",
    "salary_report_review",
    "interview_session_started",
    "answer_evaluation",
    "company_research",
    "email_draft",
    "review_application_draft",
    "linkedin_outreach",
}
ACTION_TYPES = DRAFT_TYPES | {
    "send_email",
    "search_confirmation",
    "auto_apply_approval",
    "browser_prepare",
    "browser_input",
    "browser_review",
    "application_answers_required",
}


class CapacityUnavailable(RuntimeError):
    """Retryable admission failure, before any external action."""


def validate_context(value) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized.startswith("_") or any(
                part in normalized
                for part in ("password", "credential", "api_key", "access_token", "refresh_token")
            ):
                raise ValueError(
                    "Use the account connection flow for credentials; "
                    "reserved context fields are not accepted"
                )
            validate_context(child)
    elif isinstance(value, list):
        for child in value:
            validate_context(child)


def validate_approval(pending: dict, edits: dict) -> dict:
    action = pending.get("type") or pending.get("action_type")
    if action not in ACTION_TYPES:
        raise ValueError(f"Unsupported approval action: {action}")
    if action == "auto_apply_approval" and any(
        item.get("action") not in {"apply_browser", "send_email"}
        for item in pending.get("actions_pending", [])
    ):
        raise ValueError("This batch contains an unsupported action; review it separately")
    if action == "application_answers_required":
        if set(edits) - {"answers"}:
            raise ValueError("Only answers may be provided for this action")
        answers = edits.get("answers")
        if not isinstance(answers, dict) or not answers:
            raise ValueError("Provide an answer for each requested field")
        result = copy.deepcopy(pending)
        result["answers"] = answers
        return result
    if set(edits) - {"body"}:
        raise ValueError("Only draft text may be edited; targets and artifacts are immutable")
    if edits and action not in {"send_email", "resume_ready", "cover_letter_review"}:
        raise ValueError("This action must be reviewed again after changes")
    result = copy.deepcopy(pending)
    if edits:
        body = edits["body"]
        if not isinstance(body, str) or not body.strip() or len(body) > 20000:
            raise ValueError("Draft text must be non-empty and at most 20000 characters")
        key = "resume_markdown" if action == "resume_ready" else "body"
        result[key] = body
        if action == "resume_ready":
            # An edited preview is not the previously generated PDF.
            result["pdf_document_id"] = None
    return result


async def execute_agent(run: AgentRun, context: dict | None = None) -> dict:
    from app.agents.harness import get_harness
    from app.core.sync_db import fetch_model_settings
    from app.core.security import decrypt_api_key

    model = await asyncio.to_thread(fetch_model_settings, str(run.user_id))
    if not model:
        raise ValueError("Configure an AI model before running an agent")
    user_settings = {
        "provider": model.provider,
        "model_name": model.model_name,
        "api_key": (
            decrypt_api_key(model.api_key_enc, settings.APP_SECRET_KEY) if model.api_key_enc else ""
        ),
        "ollama_url": model.ollama_url,
    }
    harness = await get_harness()
    return await harness.run(
        user_id=str(run.user_id),
        run_id=str(run.id),
        task_type=run.agent_type,
        context={
            **(context if context is not None else (run.input or {}).get("context", {})),
            "_durable": True,
        },
        user_settings=user_settings,
    )


async def send_approved_email(
    user_id: uuid.UUID,
    run_id: uuid.UUID,
    recipient: str,
    subject: str,
    body: str,
) -> dict:
    """The single path for sending an approved email — atomic claim before
    ever calling Gmail, so two concurrent approvals of the same run cause
    exactly one Gmail call. Both workflow_service.continue_action's
    send_email branch and /email/approve/{run_id} call this; neither calls
    GmailMCPClient directly.
    """
    from app.models.db import OutboundMessage

    # One outbound_messages row per approved run — the idempotency_key is
    # the compare-and-swap key a concurrent duplicate approval collides on.
    idempotency_key = f"agent_run:{run_id}"
    body_hash = hashlib.sha256(body.encode()).hexdigest()

    async with AsyncSessionLocal() as db:
        # Ensure the ledger row exists first, then lock it. SELECT … FOR
        # UPDATE alone locks nothing while the row does not exist yet, so two
        # concurrent first approvals both inserted and the loser crashed on
        # the unique key instead of being suppressed as a duplicate. ON
        # CONFLICT makes the second insert wait for the first and do nothing.
        await db.execute(
            pg_insert(OutboundMessage)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                run_id=run_id,
                channel="email",
                recipient=recipient,
                subject=subject,
                body_hash=body_hash,
                idempotency_key=idempotency_key,
                state="draft",
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )
        message = (
            await db.execute(
                select(OutboundMessage)
                .where(OutboundMessage.idempotency_key == idempotency_key)
                .with_for_update()
            )
        ).scalar_one()
        if message.state in {"sending", "sent"}:
            return {
                "sent": message.state == "sent",
                "duplicate_suppressed": True,
                "provider_message_id": message.provider_message_id,
            }
        message.state = "sending"
        message.recipient = recipient
        message.subject = subject
        message.body_hash = body_hash
        await db.flush()
        message_id = message.id
        await db.commit()

    try:
        from app.services.gmail_service import GmailMCPClient

        result = await asyncio.to_thread(
            GmailMCPClient(str(user_id)).send_message,
            to=recipient,
            subject=subject,
            body=body,
        )
        provider_message_id = result.get("id") if isinstance(result, dict) else str(result)
    except Exception:
        async with AsyncSessionLocal() as db:
            msg = await db.get(OutboundMessage, message_id, with_for_update=True)
            if msg and msg.state == "sending":
                msg.state = "outcome_unknown"
            await db.commit()
        raise

    async with AsyncSessionLocal() as db:
        msg = await db.get(OutboundMessage, message_id, with_for_update=True)
        if msg:
            msg.state = "sent"
            msg.provider_message_id = provider_message_id
            msg.sent_at = datetime.now(timezone.utc)
        await db.commit()
    return {"sent": True, "provider_message_id": provider_message_id}


async def continue_action(run: AgentRun, pending: dict) -> dict:
    action = pending.get("type")
    if action in DRAFT_TYPES:
        return {"status": "completed", "result": {**pending, "reviewed": True}}
    if action == "search_confirmation":
        from app.agents.orchestrator import orchestrator

        params = pending.get("interpretation")
        if not isinstance(params, dict):
            raise ValueError("Search confirmation is missing its interpretation")
        return await orchestrator.ainvoke(
            {
                "user_id": str(run.user_id),
                "run_id": str(run.id),
                "task_type": "job_search",
                "status": "running",
                "messages": [],
                "context": {
                    "search_query": params.get("role_title", ""),
                    "location": params.get("location", "Remote"),
                    "max_results": 10,
                    "_durable": True,
                },
            }
        )
    if action == "send_email":
        recipient = pending.get("recipient") or pending.get("to")
        if not recipient or not pending.get("subject") or not pending.get("body"):
            raise ValueError("Missing email fields")
        result = await send_approved_email(
            run.user_id, run.id, recipient, pending["subject"], pending["body"]
        )
        return {"status": "completed", "result": result}
    if action == "application_answers_required":
        from app.applications import profile_service
        from app.services.application_workflow import run_application_stage

        answers = pending.get("answers") or {}
        fields_by_id = {f.get("field_id"): f for f in pending.get("fields", [])}
        async with AsyncSessionLocal() as db:
            for field_id, value in answers.items():
                meta = fields_by_id.get(field_id, {})
                question_key = meta.get("question_key") or field_id
                await profile_service.save_approved_answer(
                    db,
                    run.user_id,
                    question_key,
                    meta.get("label", question_key),
                    value,
                )
            await db.commit()
        # Re-attempt preparation now that the answers are saved — the
        # resolver will find them this time, or surface whatever is still
        # missing as a fresh checkpoint.
        resumed = {
            k: v for k, v in pending.items() if k not in {"answers", "fields", "type", "message"}
        }
        resumed["type"] = "browser_input"
        return await run_application_stage(run, resumed)
    if action == "auto_apply_approval":
        return await _start_approved_batch(run, pending)
    if action in {"browser_prepare", "browser_input", "browser_review"}:
        from app.services.application_workflow import run_application_stage

        return await run_application_stage(run, pending)
    raise ValueError("Unsupported continuation")


async def _start_approved_batch(run: AgentRun, pending: dict) -> dict:
    """Fan an approved auto-apply batch out into durable workflows.

    Each application becomes its own AutoApplyWorkflow (which reserves the
    ApplicationAttempt and owns the idempotent-submit ledger), and each email
    its own AgentRunWorkflow that starts at the approved send. Workflow ids
    are derived from the application / child run, so a retried approval can
    never start a second workflow for the same item.
    """
    from app.workflows.starters import start_agent_run, start_auto_apply

    async with AsyncSessionLocal() as db:
        parent = await db.get(AgentRun, run.id, with_for_update=True)
        if parent is None:
            raise ValueError("Parent run is no longer available")
        existing = (parent.output or {}).get("child_run_ids")
        if existing:
            return {"status": "completed", "result": {"child_run_ids": existing}}

    children: list[str] = []
    applications: list[str] = []
    skipped: list[dict] = []
    for item in pending.get("actions_pending", [])[:20]:
        kind = item.get("action")
        if kind == "apply_browser":
            job_application_id = item.get("job_application_id")
            if not job_application_id:
                skipped.append(
                    {
                        "action": kind,
                        "job_url": item.get("job_url"),
                        "reason": "Missing job_application_id; cannot reserve a submission attempt",
                    }
                )
                continue
            async with AsyncSessionLocal() as db:
                attempt = (
                    await db.execute(
                        select(ApplicationAttempt).where(
                            ApplicationAttempt.user_id == run.user_id,
                            ApplicationAttempt.job_application_id
                            == uuid.UUID(str(job_application_id)),
                        )
                    )
                ).scalar_one_or_none()
            if attempt and attempt.state in ACTIVE_SUBMISSION_STATES:
                skipped.append(
                    {
                        "action": kind,
                        "job_application_id": str(job_application_id),
                        "reason": f"An application attempt is already {attempt.state}",
                    }
                )
                continue
            started = await start_auto_apply(run.user_id, uuid.UUID(str(job_application_id)))
            applications.append(started["workflow_id"])
        elif kind == "send_email":
            child_id = uuid.uuid4()
            async with AsyncSessionLocal() as db:
                db.add(
                    AgentRun(
                        id=child_id,
                        user_id=run.user_id,
                        agent_type="email",
                        status="queued",
                        input={"parent_run_id": str(run.id)},
                    )
                )
                await db.commit()
            await start_agent_run(
                child_id,
                run.user_id,
                initial_continuation={**item, "type": "send_email"},
            )
            children.append(str(child_id))

    async with AsyncSessionLocal() as db:
        parent = await db.get(AgentRun, run.id, with_for_update=True)
        if parent is not None:
            parent.output = {
                **(parent.output or {}),
                "child_run_ids": children,
                "application_workflows": applications,
                "skipped_actions": skipped,
            }
            await db.commit()
    return {
        "status": "completed",
        "result": {
            "child_run_ids": children,
            "application_workflows": applications,
            "skipped_actions": skipped,
            "message": "Approved actions started; each application still needs your final review",
        },
    }
