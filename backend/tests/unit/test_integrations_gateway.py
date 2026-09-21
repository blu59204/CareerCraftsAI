import hashlib
import hmac
from uuid import UUID

import httpx
import pytest

from app.integrations.exceptions import ConnectionNotFoundError, IntegrationActionError
from app.integrations.mock import MockIntegrationGateway
from app.integrations.nango import NangoIntegrationGateway
from app.integrations.providers import provider_config_key, provider_for_config_key
from app.integrations.validation import InvalidReturnPath, validate_return_path
from app.integrations.webhooks import verify_nango_webhook, webhook_event_hash

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
CONFIG_KEYS = {"gmail": "career-gmail"}


def test_return_path_rejects_open_redirects() -> None:
    assert (
        validate_return_path("/settings/integrations?provider=gmail")
        == "/settings/integrations?provider=gmail"
    )
    for value in (
        "https://attacker.example",
        "//attacker.example",
        "/\\attacker",
        "login",
    ):
        with pytest.raises(InvalidReturnPath):
            validate_return_path(value)


def test_provider_config_keys_are_deployment_configured() -> None:
    assert provider_config_key("gmail", CONFIG_KEYS) == "career-gmail"
    assert provider_for_config_key("career-gmail", CONFIG_KEYS) == "gmail"
    with pytest.raises(ValueError, match="not configured"):
        provider_config_key("google_drive", CONFIG_KEYS)


def test_webhook_hmac_and_hash_are_raw_body_based() -> None:
    body = b'{"type":"auth"}'
    signature = hmac.new(b"webhook-key", body, hashlib.sha256).hexdigest()
    assert verify_nango_webhook(body=body, signature=signature, signing_key="webhook-key")
    assert not verify_nango_webhook(
        body=body + b" ", signature=signature, signing_key="webhook-key"
    )
    assert webhook_event_hash(body) == hashlib.sha256(body).hexdigest()


@pytest.mark.asyncio
async def test_nango_connect_session_uses_backend_bearer_auth_only() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/connect/sessions"
        assert request.headers["Authorization"] == "Bearer server-secret"
        assert b'"allowed_integrations":["career-gmail"]' in request.content
        assert b'"end_user_id":"00000000-0000-0000-0000-000000000001"' in request.content
        return httpx.Response(
            201,
            json={
                "data": {
                    "token": "short-lived-session-token",
                    "connect_link": "https://connect.nango.dev/session",
                    "expires_at": "2026-01-01T00:00:00Z",
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = NangoIntegrationGateway(
        base_url="https://api.nango.dev",
        secret_key="server-secret",
        provider_config_keys=CONFIG_KEYS,
        client=client,
    )
    session = await gateway.create_connect_session(
        user_id=USER_ID, provider="gmail", return_path="/settings/integrations"
    )
    await client.aclose()
    assert session.connect_session_token == "short-lived-session-token"
    assert session.connect_link == "https://connect.nango.dev/session"


@pytest.mark.asyncio
async def test_connect_session_retries_transient_network_failure() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("transient network drop", request=request)
        return httpx.Response(
            201,
            json={
                "data": {
                    "token": "short-lived-session-token",
                    "connect_link": "https://connect.nango.dev/session",
                    "expires_at": "2026-01-01T00:00:00Z",
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = NangoIntegrationGateway(
        base_url="https://api.nango.dev",
        secret_key="server-secret",
        provider_config_keys=CONFIG_KEYS,
        client=client,
    )
    session = await gateway.create_connect_session(
        user_id=USER_ID, provider="gmail", return_path="/settings/integrations"
    )
    await client.aclose()
    assert calls == 2  # first attempt dropped, retry succeeded
    assert session.connect_session_token == "short-lived-session-token"


@pytest.mark.asyncio
async def test_nango_action_does_not_retry_external_mutation() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if request.url.path == "/connections":
            return httpx.Response(
                200,
                json={
                    "connections": [
                        {
                            "connection_id": "conn-1",
                            "provider_config_key": "career-gmail",
                            "created": "2026-01-01T00:00:00Z",
                            "errors": [],
                        }
                    ]
                },
            )
        return httpx.Response(503, json={"error": {"code": "unavailable"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = NangoIntegrationGateway(
        base_url="https://api.nango.dev",
        secret_key="server-secret",
        provider_config_keys=CONFIG_KEYS,
        client=client,
    )
    with pytest.raises(IntegrationActionError):
        await gateway.execute_action(
            user_id=USER_ID,
            provider="gmail",
            action="send-email",
            input_data={},
            idempotency_key="attempt-1",
        )
    await client.aclose()
    assert calls == 2  # one safe connection read and one non-retried POST


@pytest.mark.asyncio
async def test_mock_gateway_enforces_connection_ownership() -> None:
    gateway = MockIntegrationGateway()
    with pytest.raises(ConnectionNotFoundError):
        await gateway.execute_action(user_id=USER_ID, provider="gmail", action="x", input_data={})


@pytest.mark.asyncio
async def test_proxy_uses_nango_connection_headers_without_retrying_mutation() -> None:
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/connections":
            return httpx.Response(
                200,
                json={
                    "connections": [
                        {
                            "connection_id": "conn-1",
                            "provider_config_key": "career-gmail",
                        }
                    ]
                },
            )
        assert request.url.path == "/proxy/gmail/v1/users/me/messages/send"
        assert request.headers["Connection-Id"] == "conn-1"
        assert request.headers["Provider-Config-Key"] == "career-gmail"
        return httpx.Response(200, json={"id": "message-1"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = NangoIntegrationGateway(
        base_url="https://api.nango.dev",
        secret_key="server-secret",
        provider_config_keys=CONFIG_KEYS,
        client=client,
    )

    result = await gateway.proxy_request(
        user_id=USER_ID,
        provider="gmail",
        method="POST",
        path="gmail/v1/users/me/messages/send",
        json_data={"raw": "message"},
    )

    assert result.data == {"id": "message-1"}
    assert len(requests) == 2
    await client.aclose()
