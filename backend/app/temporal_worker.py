"""Run with python -m app.temporal_worker. Only meaningful when
TEMPORAL_ENABLED=true — see app/core/config.py and
docs/superpowers/specs for the migration this is part of.

Mirrors app/workflow_worker.py's structure (the BullMQ worker) so both
worker processes are operable the same way; this one hosts Temporal
workflows/activities instead of polling a BullMQ queue.
"""

import asyncio
import logging
import signal

from temporalio.worker import Worker

from app.core.config import settings
from app.core.temporal_client import get_temporal_client, reset_temporal_client
from app.workflows.activities import (
    apply_answers_and_resume_activity,
    reserve_application_attempt,
    run_application_stage_activity,
    schedule_followup_activity,
)
from app.workflows.auto_apply import AutoApplyWorkflow

logger = logging.getLogger(__name__)


async def main() -> None:
    if not settings.TEMPORAL_ENABLED:
        logger.warning(
            "TEMPORAL_ENABLED is false — this worker would register with "
            "Temporal but no workflow will ever be started against it "
            "until the flag is turned on. Exiting."
        )
        return

    settings.validate_temporal_configuration()
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[AutoApplyWorkflow],
        activities=[
            reserve_application_attempt,
            run_application_stage_activity,
            apply_answers_and_resume_activity,
            schedule_followup_activity,
        ],
        max_concurrent_activities=settings.TEMPORAL_WORKER_CONCURRENCY,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # add_signal_handler isn't available on Windows' default loop —
            # Ctrl+C still raises KeyboardInterrupt, caught below.
            pass

    logger.info(
        "Temporal worker starting: address=%s namespace=%s task_queue=%s concurrency=%d",
        settings.TEMPORAL_ADDRESS,
        settings.TEMPORAL_NAMESPACE,
        settings.TEMPORAL_TASK_QUEUE,
        settings.TEMPORAL_WORKER_CONCURRENCY,
    )
    async with worker:
        try:
            await stop_event.wait()
        except KeyboardInterrupt:
            pass
    logger.info("Temporal worker shut down gracefully")
    reset_temporal_client()


if __name__ == "__main__":
    logging.basicConfig(level=settings.LOG_LEVEL)
    asyncio.run(main())
