from datetime import datetime, timezone
from typing import Any

from app.models.db import AgentRun, User

CLIENT_SAFE_AGENT_ERROR = "Agent failed"


def apply_harness_result(
    agent_run: AgentRun,
    harness_result: dict[str, Any],
) -> dict[str, Any] | None:
    """Persist a harness result onto an endpoint-created AgentRun row."""
    status = harness_result.get("status") or "failed"
    # Agent errors can include provider traces or prompts; keep persisted
    # client-visible output generic while detailed errors stay in server logs.
    if status == "failed" and harness_result.get("error"):
        output = {"error": CLIENT_SAFE_AGENT_ERROR}
    else:
        output = harness_result.get("result") or harness_result.get("pending_action") or None
    agent_run.status = status
    agent_run.output = output
    agent_run.duration_ms = harness_result.get("duration_ms")
    if status in {"completed", "failed", "awaiting_approval"}:
        agent_run.completed_at = datetime.now(timezone.utc)  # noqa: UP017
    return output


async def _check_run_choices(db, user: User, context: dict[str, Any]) -> None:
    """Per-run model / resume picks must be the caller's own rows."""
    import uuid

    from fastapi import HTTPException
    from sqlalchemy import select

    from app.models.db import UserDocument, UserModelSettings

    for key, model, extra in (
        ("model_setting_id", UserModelSettings, None),
        ("resume_document_id", UserDocument, UserDocument.doc_type == "resume"),
    ):
        raw = context.get(key)
        if raw in (None, ""):
            continue
        try:
            row_id = uuid.UUID(str(raw))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid {key}") from None
        query = select(model.id).where(model.id == row_id, model.user_id == user.id)
        if extra is not None:
            query = query.where(extra)
        if (await db.execute(query)).first() is None:
            raise HTTPException(status_code=404, detail=f"{key} not found")


async def check_run_admission(db, user: User) -> None:
    """Serialize execution admission across chat, API and scheduled work.

    The caller must create its queued/running row before committing the same
    transaction. The user lock makes check + reservation atomic on all replicas.
    """
    from datetime import UTC, timedelta

    from fastapi import HTTPException
    from sqlalchemy import and_, or_, select, update

    from app.core.config import settings

    locked_user = (
        await db.execute(select(User).where(User.id == user.id).with_for_update())
    ).scalar_one_or_none()
    if locked_user is None:
        raise HTTPException(status_code=404, detail="User account not found")
    now = datetime.now(UTC)
    deletion_due = getattr(locked_user, "deletion_scheduled_for", None)
    if deletion_due is not None and deletion_due <= now:
        raise HTTPException(status_code=403, detail="Account deletion is in progress")
    # A crashed process cannot leave request/activity-owned work occupying a
    # slot forever. Durable workflows own their own recovery; only the bounded
    # chat/outreach draft paths below use this expiry.
    await db.execute(
        update(AgentRun)
        .where(
            AgentRun.user_id == user.id,
            or_(
                AgentRun.agent_type == "chat_orchestrator",
                and_(
                    AgentRun.agent_type == "email",
                    AgentRun.input["source"].astext == "application_outreach",
                ),
            ),
            AgentRun.status == "running",
            AgentRun.started_at < now - timedelta(minutes=10),
        )
        .values(
            status="failed",
            completed_at=now,
            output={"error": "Agent work interrupted"},
        )
    )
    # Applications waiting in the user's own browser (extension mode) use no
    # server capacity and can wait for hours, so they never block agents.
    active_runs = await db.execute(
        select(AgentRun.id).where(
            AgentRun.user_id == user.id,
            AgentRun.status.in_(["queued", "running"]),
            AgentRun.agent_type != "apply_prepare",
            AgentRun.agent_type != "computer_action",
        )
    )
    active_run_ids = [str(run_id) for run_id in active_runs.scalars().all()]
    max_concurrent = getattr(settings, "AGENT_MAX_CONCURRENT_PER_USER", 2)
    if len(active_run_ids) >= max_concurrent:
        raise HTTPException(
            status_code=429,
            detail={
                "message": f"Max {max_concurrent} concurrent agent runs reached. "
                "Wait for current runs to complete.",
                "run_ids": active_run_ids,
            },
        )


async def queue_agent_run(db, user: User, task_type: str, context: dict[str, Any]) -> str:
    """Create a queued agent run and start its durable AgentRunWorkflow.

    The one way an API route starts agent work: it enforces the per-user
    concurrency cap, commits the row before the workflow's first activity
    reads it, and returns the run id for the client to poll or stream.
    """
    import uuid

    from fastapi import HTTPException

    from app.services.workflow_service import validate_context
    from app.workflows.starters import WorkflowUnavailable, start_agent_run

    try:
        validate_context(context)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    await _check_run_choices(db, user, context)

    await check_run_admission(db, user)

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=user.id,
        agent_type=task_type,
        status="queued",
        input={"task_type": task_type, "context": context},
    )
    db.add(agent_run)
    # Committed before the workflow starts: its first activity reads the row.
    await db.commit()

    try:
        await start_agent_run(run_id, user.id)
    except WorkflowUnavailable as exc:
        agent_run.status = "failed"
        agent_run.output = {"error": "Agent service unavailable — try again shortly"}
        agent_run.completed_at = datetime.now(timezone.utc)  # noqa: UP017
        await db.commit()
        raise HTTPException(status_code=503, detail="Agent service unavailable") from exc
    return run_id
