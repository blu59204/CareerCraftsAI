"""Reusable Temporal client. Feature-flagged via settings.TEMPORAL_ENABLED —
callers (API routes, the Temporal worker) must check that flag themselves;
this module doesn't, so it stays usable from tests that want to exercise a
real/local Temporal server regardless of the flag's value.
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
        client_cert=client_cert, client_private_key=client_key,
        server_root_ca_cert=server_root_ca_cert,
    )


async def get_temporal_client() -> Client:
    """Return a shared, lazily-connected Temporal client.

    Raises whatever temporalio raises on connection failure — callers decide
    how to degrade (the health check reports this separately; API routes
    that start/signal workflows let the error surface as a 502/503 rather
    than silently falling back, since TEMPORAL_ENABLED being true is an
    explicit operator choice).
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
            settings.TEMPORAL_ADDRESS, settings.TEMPORAL_NAMESPACE,
        )
    return _client


async def check_temporal_health() -> dict:
    """Used by /health — must never raise; a Temporal outage should never
    make the whole API unavailable when TEMPORAL_ENABLED is false, and even
    when true, health reporting stays best-effort."""
    if not settings.TEMPORAL_ENABLED:
        return {"enabled": False, "connected": False}
    try:
        client = await get_temporal_client()
        await client.service_client.check_health()
        return {"enabled": True, "connected": True}
    except Exception as exc:
        logger.warning("Temporal health check failed: %s", exc)
        return {"enabled": True, "connected": False, "error": str(exc)}


def reset_temporal_client() -> None:
    """Test/worker-shutdown hook — drops the cached client so the next
    get_temporal_client() call reconnects."""
    global _client
    _client = None
