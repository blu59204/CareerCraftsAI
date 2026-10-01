"""Workflows started by Temporal Schedules, and the code that registers
those Schedules."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.job_activities import (
        daily_search_activity,
        inbox_status_activity,
        list_daily_search_users_activity,
        list_inbox_tracking_users_activity,
        maintenance_activity,
        refresh_job_catalog_activity,
    )

logger = logging.getLogger(__name__)

_RETRY = RetryPolicy(initial_interval=timedelta(minutes=1), maximum_attempts=3)


# Members searched at once. Each search runs browser automation on its own
# member's key, so this bounds worker load, not anyone's spend.
_DAILY_SEARCH_BATCH = 5


@workflow.defn
class DailyUserSearchWorkflow:
    """One member's daily search, with its own timeout and retries, so a slow
    or failing member never holds up or restarts anyone else's."""

    @workflow.run
    async def run(self, user_id: str) -> dict:
        return await workflow.execute_activity(
            daily_search_activity,
            {"user_id": user_id},
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=_RETRY,
        )


@workflow.defn
class DailySearchWorkflow:
    @workflow.run
    async def run(self) -> dict:
        listed = await workflow.execute_activity(
            list_daily_search_users_activity,
            {},
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_RETRY,
        )
        user_ids: list[str] = listed.get("user_ids", [])
        parent_id = workflow.info().workflow_id
        failed = 0
        for start in range(0, len(user_ids), _DAILY_SEARCH_BATCH):
            batch = user_ids[start : start + _DAILY_SEARCH_BATCH]
            results = await asyncio.gather(
                *(
                    workflow.execute_child_workflow(
                        DailyUserSearchWorkflow.run,
                        user_id,
                        id=f"{parent_id}/user/{user_id}",
                    )
                    for user_id in batch
                ),
                return_exceptions=True,
            )
            failed += sum(isinstance(result, BaseException) for result in results)
        return {"users": len(user_ids), "failed": failed}


@workflow.defn
class InboxStatusWorkflow:
    """Scan each opted-in member's Gmail for replies to their applications.
    One activity per member, five at a time, each with its own timeout and
    retries, so one mailbox failing never holds up or restarts another."""

    @workflow.run
    async def run(self) -> dict:
        listed = await workflow.execute_activity(
            list_inbox_tracking_users_activity,
            {},
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_RETRY,
        )
        user_ids: list[str] = listed.get("user_ids", [])
        failed = 0
        for start in range(0, len(user_ids), _DAILY_SEARCH_BATCH):
            batch = user_ids[start : start + _DAILY_SEARCH_BATCH]
            results = await asyncio.gather(
                *(
                    workflow.execute_activity(
                        inbox_status_activity,
                        {"user_id": user_id},
                        start_to_close_timeout=timedelta(minutes=10),
                        retry_policy=_RETRY,
                    )
                    for user_id in batch
                ),
                return_exceptions=True,
            )
            failed += sum(isinstance(result, BaseException) for result in results)
        return {"users": len(user_ids), "failed": failed}


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


@workflow.defn
class JobCatalogRefreshWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            refresh_job_catalog_activity,
            {},
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=_RETRY,
        )


def schedule_specs() -> list[tuple[str, type, timedelta]]:
    """(schedule id, workflow class, interval) for every recurring job."""
    from app.core.config import settings

    specs = [
        ("public-job-catalog-refresh", JobCatalogRefreshWorkflow, timedelta(hours=1)),
        (
            "daily-job-search",
            DailySearchWorkflow,
            timedelta(hours=settings.DAILY_SEARCH_INTERVAL_HOURS),
        ),
        (
            "inbox-status-check",
            InboxStatusWorkflow,
            timedelta(hours=settings.INBOX_STATUS_INTERVAL_HOURS),
        ),
        (
            "maintenance",
            MaintenanceWorkflow,
            timedelta(seconds=settings.MAINTENANCE_INTERVAL_SECONDS),
        ),
    ]
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
