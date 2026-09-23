"""Run with python -m app.workflow_worker. Scale this service independently."""
import asyncio
import logging

from bullmq import Queue, Worker

from app.core.config import settings
from app.services.queue_service import _bullmq_connection
from app.services.sandbox_service import reap_sessions
from app.services.workflow_service import dispatch_pending, execute_task, recover_expired_tasks

logger = logging.getLogger(__name__)


async def main():
    options = {"connection": _bullmq_connection()}
    queue = Queue(settings.WORKFLOW_QUEUE, options)

    async def process(job, token):
        await execute_task(job.data["task_id"])

    worker = Worker(settings.WORKFLOW_QUEUE, process, {
        **options, "concurrency": settings.WORKFLOW_WORKER_CONCURRENCY,
        "lockDuration": 60000,
    })
    try:
        while True:
            # Each step is isolated so a queue outage cannot starve recovery
            # or strand browser sandboxes.
            try:
                await recover_expired_tasks()
            except Exception:
                logger.exception("Workflow recovery unavailable; retrying")
            try:
                await dispatch_pending(queue)
            except Exception:
                logger.exception("Workflow dispatcher unavailable; retrying")
            try:
                await reap_sessions()
            except Exception:
                logger.exception("Browser reaper unavailable; retrying")
            await asyncio.sleep(settings.WORKFLOW_DISPATCH_INTERVAL_S)
    finally:
        await worker.close()
        await queue.close()


if __name__ == "__main__":
    logging.basicConfig(level=settings.LOG_LEVEL)
    asyncio.run(main())
