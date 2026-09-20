"""Provider-neutral contract used by application services."""

from typing import Protocol
from uuid import UUID

from app.integrations.schemas import (
    ConnectSession,
    IntegrationConnectionResult,
    IntegrationProxyResponse,
)


class IntegrationGateway(Protocol):
    def provider_config_key(self, provider: str) -> str: ...

    async def create_connect_session(
        self, *, user_id: UUID, provider: str, return_path: str
    ) -> ConnectSession: ...

    async def get_connection(
        self, *, user_id: UUID, provider: str
    ) -> IntegrationConnectionResult | None: ...

    async def list_connections(self, *, user_id: UUID) -> list[IntegrationConnectionResult]: ...

    async def revoke_connection(self, *, user_id: UUID, provider: str) -> None: ...

    async def execute_action(
        self,
        *,
        user_id: UUID,
        provider: str,
        action: str,
        input_data: dict,
        idempotency_key: str | None = None,
    ) -> dict: ...

    async def proxy_request(
        self,
        *,
        user_id: UUID,
        provider: str,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        json_data: dict | None = None,
        content: bytes | None = None,
    ) -> IntegrationProxyResponse: ...
