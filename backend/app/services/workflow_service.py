"""Durable commands: API transactions enqueue intent; isolated workers execute it.

BullMQ is delivery, PostgreSQL is the authoritative execution/approval ledger.
External writes are never automatically replayed after an uncertain outcome.
"""
from __future__ import annotations

import asyncio
import copy
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.event_bus import publish, suppress_terminal_events
from app.models.db import AgentRun, User, WorkflowTask

DRAFT_TYPES = {
    "resume_ready", "cover_letter_review", "linkedin_edits", "interview_prep",
    "salary_report_review", "interview_session_started", "answer_evaluation",
    "company_research", "email_draft", "review_application_draft",
}
ACTION_TYPES = DRAFT_TYPES | {
    "send_email", "search_confirmation", "auto_apply_approval", "browser_prepare",
    "browser_input", "browser_review",
}


class CapacityUnavailable(RuntimeError):
    """Retryable admission failure, before any external action."""


def validate_context(value) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized.startswith("_") or any(
                part in normalized for part in ("password", "credential", "api_key", "access_token", "refresh_token")
            ):
                raise ValueError("Use the account connection flow for credentials; reserved context fields are not accepted")
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


def add_task(db, run: AgentRun, kind: str, payload: dict) -> WorkflowTask:
    task = WorkflowTask(
        id=uuid.uuid4(), run_id=run.id, user_id=run.user_id,
        kind=kind, payload=copy.deepcopy(payload), status="pending",
    )
    db.add(task)
    return task


async def dispatch_pending(queue) -> int:
    """Outbox publication is replayable using a stable BullMQ job ID."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        tasks = (await db.execute(
            select(WorkflowTask).where(
                WorkflowTask.status.in_(["pending", "dispatched"]),
                WorkflowTask.available_at <= now,
            ).order_by(WorkflowTask.available_at).limit(20).with_for_update(skip_locked=True)
        )).scalars().all()
        for task in tasks:
            await queue.add("workflow", {"task_id": str(task.id)}, {
                "jobId": str(task.id), "attempts": 3,
                "backoff": {"type": "exponential", "delay": 5000},
                "removeOnComplete": True, "removeOnFail": True,
            })
            task.status = "dispatched"
            task.available_at = now + timedelta(seconds=60)
        await db.commit()
        return len(tasks)


async def recover_expired_tasks() -> None:
    """An abandoned execution may have written externally. Fail closed, never replay."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        tasks = (await db.execute(select(WorkflowTask).where(
            WorkflowTask.status == "running",
            or_(WorkflowTask.lease_until.is_(None), WorkflowTask.lease_until < now),
        ).with_for_update(skip_locked=True).limit(50))).scalars().all()
        for task in tasks:
            run = await db.get(AgentRun, task.run_id, with_for_update=True)
            task.status = "failed"
            task.error = "Worker lease expired; verify external outcome before starting again"
            if run and run.status == "running":
                run.status = "failed"
                run.output = {"error": task.error, "outcome": "unknown"}
                run.completed_at = datetime.now(timezone.utc)
        await db.commit()


async def execute_task(task_id: str) -> None:
    try:
        task_uuid = uuid.UUID(task_id)
    except (ValueError, AttributeError, TypeError):
        return  # Poisoned queue entry; no ledger row can match it.
    async with AsyncSessionLocal() as db:
        task = await db.get(WorkflowTask, task_uuid, with_for_update=True)
        if not task or task.status not in {"pending", "dispatched"}:
            return
        await db.execute(select(User.id).where(User.id == task.user_id).with_for_update())
        run = await db.get(AgentRun, task.run_id, with_for_update=True)
        if not run or run.user_id != task.user_id or run.status != "queued":
            task.status = "completed"
            await db.commit()
            return
        active = (await db.execute(select(func.count()).select_from(AgentRun).where(
            AgentRun.user_id == run.user_id, AgentRun.status == "running",
        ))).scalar_one()
        if active >= settings.AGENT_MAX_CONCURRENT_PER_USER:
            task.status = "pending"
            task.available_at = datetime.now(timezone.utc) + timedelta(seconds=10)
            await db.commit()
            return
        task.status = "running"
        task.lease_until = datetime.now(timezone.utc) + timedelta(seconds=settings.WORKFLOW_TASK_TIMEOUT_S + 120)
        run.status = "running"
        await db.commit()

    started = time.monotonic()
    token = suppress_terminal_events.set(True)
    try:
        async with asyncio.timeout(settings.WORKFLOW_TASK_TIMEOUT_S):
            if task.kind == "execute":
                result = await execute_agent(run)
            else:
                result = await continue_action(run, task.payload)
    except CapacityUnavailable:
        async with AsyncSessionLocal() as db:
            row = await db.get(WorkflowTask, task.id, with_for_update=True)
            current = await db.get(AgentRun, run.id, with_for_update=True)
            if row is None or current is None:
                return  # Ledger row deleted; nothing to requeue.
            if row.status != "running" or current.status != "running":
                return  # Stale worker must not resurrect cancellation/recovery.
            row.status = "pending"
            row.available_at = datetime.now(timezone.utc) + timedelta(seconds=15)
            row.lease_until = None
            current.status = "queued"
            await db.commit()
        return
    except Exception:
        # Provider errors can include secrets and authenticated URLs.
        result = {"status": "failed", "error": "Workflow failed or timed out; review the external outcome before retrying"}
    finally:
        suppress_terminal_events.reset(token)

    async with AsyncSessionLocal() as db:
        row = await db.get(WorkflowTask, task.id, with_for_update=True)
        current = await db.get(AgentRun, run.id, with_for_update=True)
        if row is None or current is None:
            return  # Ledger row deleted; nothing to record.
        if row.status != "running" or current.status != "running":
            return  # Stale worker must not overwrite cancellation/recovery.
        status = result.get("status", "failed")
        current.status = status if status in {"completed", "awaiting_approval", "failed"} else "failed"
        output = result.get("pending_action") if current.status == "awaiting_approval" else result.get("result")
        current.output = output or {"error": result.get("error", "Workflow produced no result")}
        current.duration_ms = int((time.monotonic() - started) * 1000)
        if result.get("tokens_used") is not None:
            current.tokens_used = result["tokens_used"]
        current.completed_at = None if current.status == "awaiting_approval" else datetime.now(timezone.utc)
        row.status = "failed" if current.status == "failed" else "completed"
        row.error = result.get("error")
        row.lease_until = None
        await db.commit()
        event = {"completed": "complete", "awaiting_approval": "checkpoint", "failed": "error"}[current.status]
        publish(str(run.id), event, current.output)


async def execute_agent(run: AgentRun, context: dict | None = None) -> dict:
    from app.agents.harness import get_harness
    from app.core.sync_db import fetch_model_settings
    from app.core.security import decrypt_api_key

    model = await asyncio.to_thread(fetch_model_settings, str(run.user_id))
    if not model:
        raise ValueError("Configure an AI model before running an agent")
    user_settings = {
        "provider": model.provider, "model_name": model.model_name,
        "api_key": decrypt_api_key(model.api_key_enc, settings.APP_SECRET_KEY) if model.api_key_enc else "",
        "ollama_url": model.ollama_url,
    }
    harness = await get_harness()
    return await harness.run(
        user_id=str(run.user_id), run_id=str(run.id), task_type=run.agent_type,
        context={**(context if context is not None else (run.input or {}).get("context", {})), "_durable": True},
        user_settings=user_settings,
    )


async def continue_action(run: AgentRun, pending: dict) -> dict:
    action = pending.get("type")
    if action in DRAFT_TYPES:
        return {"status": "completed", "result": {**pending, "reviewed": True}}
    if action == "search_confirmation":
        from app.agents.orchestrator import orchestrator
        params = pending.get("interpretation")
        if not isinstance(params, dict):
            raise ValueError("Search confirmation is missing its interpretation")
        return await orchestrator.ainvoke({
            "user_id": str(run.user_id), "run_id": str(run.id), "task_type": "job_search",
            "status": "running", "messages": [], "context": {
                "search_query": params.get("role_title", ""), "location": params.get("location", "Remote"),
                "max_results": 10, "_durable": True,
            },
        })
    if action == "send_email":
        from app.services.gmail_service import GmailMCPClient
        recipient = pending.get("recipient") or pending.get("to")
        if not recipient or not pending.get("subject") or not pending.get("body"):
            raise ValueError("Missing email fields")
        receipt = await asyncio.to_thread(
            GmailMCPClient(str(run.user_id)).send_message,
            to=recipient, subject=pending["subject"], body=pending["body"],
        )
        return {"status": "completed", "result": {"sent": True, "receipt": receipt}}
    if action == "auto_apply_approval":
        children = []
        async with AsyncSessionLocal() as db:
            parent = await db.get(AgentRun, run.id, with_for_update=True)
            if parent is None:
                raise ValueError("Parent run is no longer available")
            # Child creation and the parent checkpoint are one transaction.
            existing = (parent.output or {}).get("child_run_ids")
            if existing:
                return {"status": "completed", "result": {"child_run_ids": existing}}
            for item in pending.get("actions_pending", [])[:20]:
                kind = item.get("action")
                if kind not in {"apply_browser", "send_email"}:
                    continue
                child = AgentRun(id=uuid.uuid4(), user_id=run.user_id,
                                 agent_type="auto_apply" if kind == "apply_browser" else "email",
                                 status="queued", input={"parent_run_id": str(run.id)})
                db.add(child)
                await db.flush()
                add_task(db, child, "continue", {
                    **item, "type": "browser_prepare" if kind == "apply_browser" else "send_email",
                })
                children.append(str(child.id))
            parent.output = {**(parent.output or {}), "child_run_ids": children}
            await db.commit()
        return {"status": "completed", "result": {
            "child_run_ids": children, "message": "Approved actions queued; each browser form requires final review",
        }}
    if action in {"browser_prepare", "browser_input", "browser_review"}:
        from app.services.application_workflow import run_application_stage
        return await run_application_stage(run, pending)
    raise ValueError("Unsupported continuation")
