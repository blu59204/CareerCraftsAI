"""Workflow/activities hosted by app/notification_worker.py — kept separate
from app/workflows/registry.py because these run on their own task queues,
polled by a separate worker process (possibly on different hardware), not
the main careercraft task queue."""

from app.workflows.notification_activities import (
    create_notification_activity,
    mark_delivery_dead_activity,
    send_notification_email_activity,
)
from app.workflows.notification_workflow import NotificationWorkflow

NOTIFICATION_WORKFLOWS = [NotificationWorkflow]

# Hosted on the main "notifications" queue.
NOTIFICATION_ACTIVITIES = [
    create_notification_activity,
    mark_delivery_dead_activity,
]

# Hosted on the separate, rate-limited "notifications-email" queue.
NOTIFICATION_EMAIL_ACTIVITIES = [
    send_notification_email_activity,
]
