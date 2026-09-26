"""Shared Temporal client. Temporal executes every agent run, job search,
follow-up and recurring job, so the API and the worker both connect here.
"""

from __future__ import annotations

import logging

from temporalio.client import Client, TLSConfig

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def _tls_config() -> TLSConfig | None:
    """None means plaintext — fine for a local/self-hosted dev server.
    Temporal Cloud requires mTLS, so both cert and key must be set together."""
    if not settings.TEMPORAL_TLS_CERT_PATH or not settings.TEMPORAL_TLS_KEY_PATH:
        return None
    with open(settings.TEMPORAL_TLS_CERT_PATH, "rb") as f:
        client_cert = f.read()
    with open(settings.TEMPORAL_TLS_KEY_PATH, "rb") as f:
        client_key = f.read()
    server_root_ca_cert = None
    if settings.TEMPORAL_TLS_CA_PATH:
        with open(settings.TEMPORAL_TLS_CA_PATH, "rb") as f:
            server_root_ca_cert = f.read()
    return TLSConfig(
        client_cert=client_cert,
        client_private_key=client_key,
        server_root_ca_cert=server_root_ca_cert,
    )


async def get_temporal_client() -> Client:
    """Return a shared, lazily-connected Temporal client.

    Raises whatever temporalio raises on connection failure — API routes
    that start/signal workflows turn that into a 503 so the user sees that
    the job did not start, instead of a run stuck in "queued" forever.
    """
    global _client
    if _client is None:
        _client = await Client.connect(
            settings.TEMPORAL_ADDRESS,
            namespace=settings.TEMPORAL_NAMESPACE,
            tls=_tls_config(),
        )
        logger.info(
            "Connected to Temporal at %s (namespace=%s)",
            settings.TEMPORAL_ADDRESS,
            settings.TEMPORAL_NAMESPACE,
        )
    return _client


async def check_temporal_health() -> dict:
    """Used by /health — must never raise. Also reports whether any worker is
    polling the task queue: a reachable server with no worker is exactly the
    "workflows are never scheduled" failure mode."""
    try:
        client = await get_temporal_client()
        await client.service_client.check_health()
    except Exception as exc:
        logger.warning("Temporal health check failed: %s", exc)
        reset_temporal_client()
        return {"connected": False, "workers": 0, "error": type(exc).__name__}

    workers = await _count_task_queue_pollers(client)
    return {"connected": True, "workers": workers, "task_queue": settings.TEMPORAL_TASK_QUEUE}


async def _count_task_queue_pollers(client: Client) -> int | None:
    """Pollers seen on the workflow task queue recently; None if unknown."""
    try:
        from temporalio.api.enums.v1 import TaskQueueType
        from temporalio.api.taskqueue.v1 import TaskQueue
        from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest

        response = await client.workflow_service.describe_task_queue(
            DescribeTaskQueueRequest(
                namespace=settings.TEMPORAL_NAMESPACE,
                task_queue=TaskQueue(name=settings.TEMPORAL_TASK_QUEUE),
                task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW,
            )
        )
        return len(response.pollers)
    except Exception as exc:
        logger.debug("Temporal task-queue describe failed: %s", exc)
        return None


def reset_temporal_client() -> None:
    """Test/worker-shutdown hook — drops the cached client so the next
    get_temporal_client() call reconnects."""
    global _client
    _client = None
