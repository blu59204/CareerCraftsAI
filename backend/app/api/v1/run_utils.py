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


async def queue_agent_run(db, user: User, task_type: str, context: dict[str, Any]) -> str:
    """Create a queued agent run and start its durable AgentRunWorkflow.

    The one way an API route starts agent work: it enforces the per-user
    concurrency cap, commits the row before the workflow's first activity
    reads it, and returns the run id for the client to poll or stream.
    """
    import uuid

    from fastapi import HTTPException
    from sqlalchemy import select

    from app.core.config import settings
    from app.services.workflow_service import validate_context
    from app.workflows.starters import WorkflowUnavailable, start_agent_run

    try:
        validate_context(context)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    # Serialize admission for this user across all API replicas.
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    # Applications waiting in the user's own browser (extension mode) use no
    # server capacity and can wait for hours, so they never block agents.
    active_runs = await db.execute(
        select(AgentRun.id).where(
            AgentRun.user_id == user.id,
            AgentRun.status.in_(["queued", "running"]),
            AgentRun.agent_type != "apply_prepare",
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
