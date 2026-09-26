"""Workflows started by Temporal Schedules (was the Node BullMQ scheduler),
and the code that registers those Schedules."""

from __future__ import annotations

import logging
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.job_activities import (
        daily_search_activity,
        maintenance_activity,
        status_check_activity,
    )

logger = logging.getLogger(__name__)

_RETRY = RetryPolicy(initial_interval=timedelta(minutes=1), maximum_attempts=3)


@workflow.defn
class DailySearchWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            daily_search_activity,
            {"user_id": "all"},
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=_RETRY,
        )


@workflow.defn
class StatusCheckWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            status_check_activity,
            {"user_id": "all"},
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=_RETRY,
        )


@workflow.defn
class MaintenanceWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            maintenance_activity,
            {},
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )


def schedule_specs() -> list[tuple[str, type, timedelta]]:
    """(schedule id, workflow class, interval) for every recurring job."""
    from app.core.config import settings

    specs = [
        (
            "daily-job-search",
            DailySearchWorkflow,
            timedelta(hours=settings.DAILY_SEARCH_INTERVAL_HOURS),
        ),
        (
            "maintenance",
            MaintenanceWorkflow,
            timedelta(seconds=settings.MAINTENANCE_INTERVAL_SECONDS),
        ),
    ]
    # Checking portal status needs a logged-in portal session. The server
    # only has one in server-browser mode; with the extension, the session
    # lives in the user's own browser.
    if settings.APPLY_EXECUTION_MODE == "server_browser":
        specs.append(
            (
                "application-status-check",
                StatusCheckWorkflow,
                timedelta(hours=settings.STATUS_CHECK_INTERVAL_HOURS),
            )
        )
    return specs


async def ensure_schedules(client) -> None:
    """Create or update every Schedule; delete ones no longer configured.
    Idempotent — every worker runs this at start."""
    from temporalio.client import (
        Schedule,
        ScheduleActionStartWorkflow,
        ScheduleAlreadyRunningError,
        ScheduleIntervalSpec,
        ScheduleOverlapPolicy,
        SchedulePolicy,
        ScheduleSpec,
        ScheduleUpdate,
    )
    from temporalio.service import RPCError

    from app.core.config import settings

    wanted = {}
    for schedule_id, workflow_cls, every in schedule_specs():
        wanted[schedule_id] = Schedule(
            action=ScheduleActionStartWorkflow(
                workflow_cls.run,
                id=f"scheduled/{schedule_id}",
                task_queue=settings.TEMPORAL_TASK_QUEUE,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=every)]),
            # A slow run is never stacked on by the next tick.
            policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
        )

    for schedule_id, schedule in wanted.items():
        try:
            await client.create_schedule(schedule_id, schedule)
            logger.info("Created Temporal schedule %s", schedule_id)
        except ScheduleAlreadyRunningError:
            await client.get_schedule_handle(schedule_id).update(
                lambda _input, s=schedule: ScheduleUpdate(schedule=s)
            )

    for schedule_id in ("daily-job-search", "application-status-check", "maintenance"):
        if schedule_id in wanted:
            continue
        try:
            await client.get_schedule_handle(schedule_id).delete()
            logger.info("Deleted Temporal schedule %s", schedule_id)
        except RPCError:
            pass
