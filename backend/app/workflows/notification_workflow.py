"""NotificationWorkflow — creates the in-app Notification, then fans out to
one activity per additional enabled channel (today: email only).

Started fire-and-forget from app.workflows.starters.start_notification, from
inside an already-running activity (job search / follow-up draft). Running
this as its own workflow — not inline in the caller — means a notification
or email failure never shares retry scope with, and can never cause a retry
of, the caller's own work. See create_notification_activity /
send_notification_email_activity for why each activity's own task queue and
retry policy matter.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

from app.core.config import settings

with workflow.unsafe.imports_passed_through():
    from app.workflows.notification_activities import (
        create_notification_activity,
        mark_delivery_dead_activity,
        send_notification_email_activity,
    )


@dataclass
class NotificationInput:
    user_id: str
    type: str
    title: str
    body: str | None = None
    link: str | None = None


@workflow.defn
class NotificationWorkflow:
    @workflow.run
    async def run(self, inp: NotificationInput) -> dict:
        created = await workflow.execute_activity(
            create_notification_activity,
            asdict(inp),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )

        email_delivery_id = created.get("email_delivery_id")
        if email_delivery_id:
            try:
                await workflow.execute_activity(
                    send_notification_email_activity,
                    {
                        "delivery_id": email_delivery_id,
                        "user_id": inp.user_id,
                        "title": inp.title,
                        "body": inp.body,
                    },
                    task_queue=settings.TEMPORAL_NOTIFICATION_EMAIL_TASK_QUEUE,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        backoff_coefficient=2.0,
                        maximum_interval=timedelta(minutes=5),
                        maximum_attempts=6,
                    ),
                )
            except ActivityError:
                await workflow.execute_activity(
                    mark_delivery_dead_activity,
                    {"delivery_id": email_delivery_id},
                    start_to_close_timeout=timedelta(seconds=15),
                    retry_policy=RetryPolicy(maximum_attempts=5),
                )

        return created
