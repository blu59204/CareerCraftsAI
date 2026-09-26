"""Activities for AgentRunWorkflow.

Each activity owns one agent_runs state transition and publishes the SSE
event the frontend listens for only after the row is committed, so a client
that reloads on the event always reads the new state. Heavy imports stay
inside the functions: this module is imported by workflow code (through
imports_passed_through) and must stay cheap to load.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime

from temporalio import activity
from temporalio.exceptions import ApplicationError

logger = logging.getLogger(__name__)

CLIENT_SAFE_FAILURE = "Workflow failed or timed out; review the external outcome before retrying"
_RUN_EVENT = {"completed": "complete", "awaiting_approval": "checkpoint", "failed": "error"}


async def record_run_result(run_id: str, result: dict, started: float | None = None) -> dict:
    """Write an agent result onto its agent_runs row, then publish the SSE
    event. Returns {"status", "action_type"} — never the output itself, so
    drafts and form contents stay out of Temporal's event history."""
    from app.core.database import AsyncSessionLocal
    from app.core.event_bus import publish
    from app.models.db import AgentRun

    status = result.get("status", "failed")
    status = status if status in _RUN_EVENT else "failed"
    output = result.get("pending_action") if status == "awaiting_approval" else result.get("result")
    output = output or {"error": result.get("error", "Workflow produced no result")}

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, uuid.UUID(run_id), with_for_update=True)
        if run is None:
            return {"status": "failed", "action_type": None}
        if run.status != "running":
            # Only the activity that claimed the run (status "running") may
            # record its result — never overwrite a cancellation or a
            # reconciliation that happened in the meantime.
            return {"status": run.status, "action_type": None}
        run.status = status
        run.output = output
        if started is not None:
            run.duration_ms = int((time.monotonic() - started) * 1000)
        if result.get("tokens_used") is not None:
            run.tokens_used = result["tokens_used"]
        run.completed_at = None if status == "awaiting_approval" else datetime.now(UTC)
        await db.commit()

    publish(run_id, _RUN_EVENT[status], output)
    action_type = output.get("type") if isinstance(output, dict) else None
    return {"status": status, "action_type": action_type}


async def _claim_run(run_id: str, allowed: set[str]):
    """Move the run to running if it is still in one of `allowed` states."""
    from app.core.database import AsyncSessionLocal
    from app.models.db import AgentRun

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, uuid.UUID(run_id), with_for_update=True)
        if run is None or run.status not in allowed:
            return None, (run.status if run else "failed")
        run.status = "running"
        run.completed_at = None
        await db.commit()
        await db.refresh(run)
        return run, "running"


async def _run_with_timeout(coro) -> dict:
    from app.core.config import settings
    from app.core.event_bus import suppress_terminal_events
    from app.services.workflow_service import CapacityUnavailable

    token = suppress_terminal_events.set(True)
    try:
        async with asyncio.timeout(settings.WORKFLOW_TASK_TIMEOUT_S):
            return await coro
    except CapacityUnavailable as exc:
        # Nothing external happened yet — let Temporal back off and retry.
        raise ApplicationError(str(exc), type="CapacityUnavailable") from exc
    except ValueError as exc:
        # Validation problems (no model configured, bad input) are the
        # user's to fix; the message is written for them.
        logger.info("Agent run rejected: %s", exc)
        return {"status": "failed", "error": str(exc)}
    except Exception:
        # Provider errors can include secrets and authenticated URLs.
        logger.exception("Agent run failed")
        return {"status": "failed", "error": CLIENT_SAFE_FAILURE}
    finally:
        suppress_terminal_events.reset(token)


@activity.defn
async def execute_agent_run_activity(params: dict) -> dict:
    from app.services.workflow_service import execute_agent

    run_id = params["run_id"]
    # "running" is allowed so a retry after a worker crash picks the run up.
    run, status = await _claim_run(run_id, {"queued", "running"})
    if run is None:
        return {"status": status, "action_type": None}
    started = time.monotonic()
    result = await _run_with_timeout(execute_agent(run))
    return await record_run_result(run_id, result, started)


@activity.defn
async def continue_agent_run_activity(params: dict) -> dict:
    from app.services.workflow_service import continue_action

    run_id = params["run_id"]
    # The approve endpoint moves the run to "queued" before signalling.
    run, status = await _claim_run(run_id, {"queued", "awaiting_approval"})
    if run is None:
        return {"status": status, "action_type": None}
    started = time.monotonic()
    result = await _run_with_timeout(continue_action(run, params.get("continuation") or {}))
    return await record_run_result(run_id, result, started)


@activity.defn
async def expire_agent_run_activity(params: dict) -> None:
    from app.core.database import AsyncSessionLocal
    from app.core.event_bus import publish
    from app.models.db import AgentRun

    run_id = params["run_id"]
    message = {"error": "Approval expired — run the agent again when you are ready"}
    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, uuid.UUID(run_id), with_for_update=True)
        if run is None or run.status != "awaiting_approval":
            return
        run.status = "expired"
        run.output = message
        run.completed_at = datetime.now(UTC)
        await db.commit()
    publish(run_id, "error", message)
