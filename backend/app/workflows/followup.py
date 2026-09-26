"""FollowupWorkflow — day-5 and day-12 follow-up drafts for one application.

Replaces BullMQ delayed jobs + the Redis "already scheduled" markers: the
workflow id (one per application) is the de-duplication, and the durable
timers survive worker restarts. Each due step only *drafts* an email into
an awaiting_approval run; a person approves the send.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.job_activities import draft_followup_activity


def followup_workflow_id(application_id: str) -> str:
    return f"followup/{application_id}"


@dataclass
class FollowupInput:
    user_id: str
    application_id: str
    applied_at: str  # ISO-8601 with timezone
    days: list[int] = field(default_factory=lambda: [5, 12])


@workflow.defn
class FollowupWorkflow:
    @workflow.run
    async def run(self, inp: FollowupInput) -> dict:
        applied_at = datetime.fromisoformat(inp.applied_at)
        drafted: list[int] = []
        for day in inp.days:
            wait = applied_at + timedelta(days=day) - workflow.now()
            if wait > timedelta(0):
                await workflow.sleep(wait)
            result = await workflow.execute_activity(
                draft_followup_activity,
                {"user_id": inp.user_id, "application_id": inp.application_id, "day": day},
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=30),
                    maximum_attempts=3,
                ),
            )
            if result.get("status") in {"cancelled", "not_found"}:
                return {"status": "stopped", "reason": result.get("reason"), "drafted": drafted}
            drafted.append(day)
        return {"status": "completed", "drafted": drafted}
