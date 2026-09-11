"""
agent_runs_repository — upsert agent run records from the orchestrator.

Used by orchestrator._run_agent_safely() to persist tokens_used, duration_ms,
status, output, and error after every agent node execution.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.sync_db import _get_sync_factory
from app.models.db import AgentRun

logger = logging.getLogger(__name__)


async def upsert_agent_run(
    run_id: str,
    status: str,
    output: dict | None = None,
    tokens_used: int | None = None,
    duration_ms: int | None = None,
    error: str | None = None,
) -> None:
    factory = _get_sync_factory()
    with factory() as db:
        agent_run = db.get(AgentRun, run_id)
        if agent_run is None:
            logger.debug("Agent run %s not found for upsert; creating placeholder", run_id)
            agent_run = AgentRun(
                id=run_id,
                agent_type="unknown",
                status=status,
                started_at=datetime.now(timezone.utc),
            )
            db.add(agent_run)
        agent_run.status = status
        if output is not None:
            agent_run.output = output
        if tokens_used is not None and tokens_used > 0:
            agent_run.tokens_used = tokens_used
        if duration_ms is not None:
            agent_run.duration_ms = duration_ms
        if error is not None:
            agent_run.error = error
        agent_run.completed_at = datetime.now(timezone.utc)
        db.commit()
