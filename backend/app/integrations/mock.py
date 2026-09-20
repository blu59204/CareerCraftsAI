"""In-memory gateway used by automated tests; never contacts Nango."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.integrations.exceptions import ConnectionNotFoundError
from app.integrations.gateway import IntegrationGateway
from app.integrations.providers import provider_definition
from app.integrations.schemas import ConnectSession, IntegrationConnectionResult
from app.integrations.validation import validate_return_path


class MockIntegrationGateway(IntegrationGateway):
    def __init__(self) -> None:
        self.connections: dict[tuple[UUID, str], IntegrationConnectionResult] = {}
        self.actions: list[tuple[UUID, str, str, dict, str | None]] = []

    def provider_config_key(self, provider: str) -> str:
        return f"mock-{provider_definition(provider).key}"

    async def create_connect_session(
        self, *, user_id: UUID, provider: str, return_path: str
    ) -> ConnectSession:
        definition = provider_definition(provider)
        validate_return_path(return_path)
        expiry = datetime.now(UTC) + timedelta(minutes=30)
        return ConnectSession(provider, f"test-session-{user_id}-{definition.key}", None, expiry)

    async def get_connection(
        self, *, user_id: UUID, provider: str
    ) -> IntegrationConnectionResult | None:
        provider_definition(provider)
        return self.connections.get((user_id, provider))

    async def list_connections(self, *, user_id: UUID) -> list[IntegrationConnectionResult]:
        return [
            connection for (owner, _), connection in self.connections.items() if owner == user_id
        ]

    async def revoke_connection(self, *, user_id: UUID, provider: str) -> None:
        provider_definition(provider)
        self.connections.pop((user_id, provider), None)

    async def execute_action(
        self,
        *,
        user_id: UUID,
        provider: str,
        action: str,
        input_data: dict,
        idempotency_key: str | None = None,
    ) -> dict:
        if await self.get_connection(user_id=user_id, provider=provider) is None:
            raise ConnectionNotFoundError("No connection exists for this provider")
        self.actions.append((user_id, provider, action, input_data, idempotency_key))
        return {"success": True}
