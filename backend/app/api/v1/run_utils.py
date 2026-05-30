from datetime import datetime, timezone
from typing import Any

from app.models.db import AgentRun

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
        output = (
            harness_result.get("result")
            or harness_result.get("pending_action")
            or None
        )
    agent_run.status = status
    agent_run.output = output
    agent_run.duration_ms = harness_result.get("duration_ms")
    if status in {"completed", "failed", "awaiting_approval"}:
        agent_run.completed_at = datetime.now(timezone.utc)  # noqa: UP017
    return output
