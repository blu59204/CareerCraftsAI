"""Public integration data structures. These never include OAuth credentials."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ConnectSession:
    provider: str
    connect_session_token: str
    connect_link: str | None
    expires_at: datetime


@dataclass(frozen=True)
class IntegrationConnectionResult:
    provider: str
    provider_config_key: str
    external_connection_id: str
    status: str
    connected_at: datetime | None = None
    last_synced_at: datetime | None = None
