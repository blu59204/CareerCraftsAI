"""Gateway construction and FastAPI dependency lifecycle."""

import json
from collections.abc import AsyncIterator

from fastapi import Request

from app.core.config import Settings, settings
from app.integrations.exceptions import IntegrationDisabledError
from app.integrations.gateway import IntegrationGateway
from app.integrations.nango import NangoIntegrationGateway


class DisabledIntegrationGateway(IntegrationGateway):
    def provider_config_key(self, provider: str) -> str:
        raise IntegrationDisabledError("Integrations are disabled")

    async def create_connect_session(self, **_: object):
        raise IntegrationDisabledError("Integrations are disabled")

    async def get_connection(self, **_: object):
        raise IntegrationDisabledError("Integrations are disabled")

    async def list_connections(self, **_: object):
        raise IntegrationDisabledError("Integrations are disabled")

    async def revoke_connection(self, **_: object):
        raise IntegrationDisabledError("Integrations are disabled")

    async def execute_action(self, **_: object):
        raise IntegrationDisabledError("Integrations are disabled")


def nango_provider_config_keys(config: Settings = settings) -> dict[str, str]:
    raw = getattr(config, "NANGO_PROVIDER_CONFIG_KEYS", "")
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("NANGO_PROVIDER_CONFIG_KEYS must be a JSON object") from exc
    if not isinstance(parsed, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in parsed.items()
    ):
        raise ValueError("NANGO_PROVIDER_CONFIG_KEYS must be a JSON object of strings")
    return parsed


def build_integration_gateway(config: Settings = settings) -> IntegrationGateway:
    if not config.NANGO_ENABLED:
        return DisabledIntegrationGateway()
    return NangoIntegrationGateway(
        base_url=config.NANGO_BASE_URL,
        secret_key=config.NANGO_SECRET_KEY,
        provider_config_keys=nango_provider_config_keys(config),
        timeout_s=config.NANGO_REQUEST_TIMEOUT_S,
    )


async def get_integration_gateway(
    request: Request,
) -> AsyncIterator[IntegrationGateway]:
    """Reuse an app-lifespan gateway when configured, otherwise close per request."""
    gateway = getattr(request.app.state, "integration_gateway", None)
    if gateway is not None:
        yield gateway
        return
    gateway = build_integration_gateway()
    try:
        yield gateway
    finally:
        close = getattr(gateway, "aclose", None)
        if close is not None:
            await close()
