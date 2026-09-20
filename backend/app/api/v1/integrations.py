"""Authenticated integration connection APIs and verified Nango webhooks."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.core.config import settings
from app.core.rate_limit import limiter
from app.integrations.exceptions import (
    IntegrationDisabledError,
    ProviderUnavailableError,
)
from app.integrations.factory import get_integration_gateway, nango_provider_config_keys
from app.integrations.gateway import IntegrationGateway
from app.integrations.providers import provider_definition
from app.integrations.repository import (
    apply_auth_webhook,
    get_connection,
    mark_pending,
    mark_revoked,
    reserve_webhook_event,
    sync_connection,
)
from app.integrations.repository import (
    list_connections as list_local_connections,
)
from app.integrations.validation import InvalidReturnPath, validate_return_path
from app.integrations.webhooks import verify_nango_webhook, webhook_event_hash
from app.models.db import IntegrationConnection, User

router = APIRouter(prefix="/integrations", tags=["integrations"])


class ConnectSessionRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    return_path: str = Field(default="/settings/integrations", max_length=2048)


class ConnectSessionResponse(BaseModel):
    provider: str
    connect_session_token: str
    connect_link: str | None
    expires_at: datetime


class ConnectionResponse(BaseModel):
    provider: str
    provider_config_key: str
    status: str
    connected_at: datetime | None
    last_synced_at: datetime | None


def _connection_response(connection: IntegrationConnection) -> ConnectionResponse:
    return ConnectionResponse(
        provider=connection.provider,
        provider_config_key=connection.provider_config_key,
        status=connection.status,
        connected_at=connection.connected_at,
        last_synced_at=connection.last_synced_at,
    )


def _api_error(exc: Exception) -> HTTPException:
    if isinstance(exc, IntegrationDisabledError):
        return HTTPException(
            status_code=503, detail="Integrations are currently disabled"
        )
    return HTTPException(status_code=503, detail="Integration provider is unavailable")


@router.post(
    "/connect-session",
    response_model=ConnectSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def create_connect_session(
    request: Request,
    payload: ConnectSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    gateway: IntegrationGateway = Depends(get_integration_gateway),
) -> ConnectSessionResponse:
    try:
        provider_definition(payload.provider)
        return_path = validate_return_path(payload.return_path)
        await mark_pending(
            db,
            user_id=current_user.id,
            provider=payload.provider,
            provider_config_key=gateway.provider_config_key(payload.provider),
        )
        session = await gateway.create_connect_session(
            user_id=current_user.id, provider=payload.provider, return_path=return_path
        )
        await db.commit()
    except (ValueError, InvalidReturnPath) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (IntegrationDisabledError, ProviderUnavailableError) as exc:
        await db.rollback()
        raise _api_error(exc) from exc
    return ConnectSessionResponse(
        provider=session.provider,
        connect_session_token=session.connect_session_token,
        connect_link=session.connect_link,
        expires_at=session.expires_at,
    )


@router.get("", response_model=list[ConnectionResponse])
async def list_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    gateway: IntegrationGateway = Depends(get_integration_gateway),
) -> list[ConnectionResponse]:
    try:
        remote_connections = await gateway.list_connections(user_id=current_user.id)
        connections = [
            await sync_connection(db, user_id=current_user.id, result=result)
            for result in remote_connections
        ]
        await db.commit()
    except (IntegrationDisabledError, ProviderUnavailableError) as exc:
        await db.rollback()
        raise _api_error(exc) from exc
    # Nango may not list a newly-created Connect session until its signed
    # webhook arrives. Preserve its local pending state in the interim.
    by_provider = {
        connection.provider: connection
        for connection in await list_local_connections(db, user_id=current_user.id)
    }
    by_provider.update({connection.provider: connection for connection in connections})
    return [_connection_response(by_provider[key]) for key in sorted(by_provider)]


@router.get("/{provider}", response_model=ConnectionResponse)
async def read_connection(
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionResponse:
    try:
        provider_definition(provider)
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail="Integration provider was not found"
        ) from exc
    connection = await get_connection(db, user_id=current_user.id, provider=provider)
    if connection is None:
        raise HTTPException(
            status_code=404, detail="Integration connection was not found"
        )
    return _connection_response(connection)


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def revoke_connection(
    request: Request,
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    gateway: IntegrationGateway = Depends(get_integration_gateway),
) -> Response:
    try:
        provider_definition(provider)
        await gateway.revoke_connection(user_id=current_user.id, provider=provider)
        await mark_revoked(db, user_id=current_user.id, provider=provider)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail="Integration provider was not found"
        ) from exc
    except (IntegrationDisabledError, ProviderUnavailableError) as exc:
        await db.rollback()
        raise _api_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/webhooks/nango", include_in_schema=False)
async def nango_webhook(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    if not settings.NANGO_ENABLED:
        raise HTTPException(
            status_code=503, detail="Integrations are currently disabled"
        )
    body = await request.body()
    if not verify_nango_webhook(
        body=body,
        signature=request.headers.get("X-Nango-Hmac-Sha256"),
        signing_key=settings.NANGO_WEBHOOK_SECRET,
    ):
        raise HTTPException(status_code=401, detail="Invalid integration webhook")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid integration webhook payload"
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400, detail="Invalid integration webhook payload"
        )
    event = await reserve_webhook_event(
        db,
        event_hash=webhook_event_hash(body),
        event_type=(
            payload.get("type") if isinstance(payload.get("type"), str) else None
        ),
        connection_id=(
            payload.get("connectionId")
            if isinstance(payload.get("connectionId"), str)
            else None
        ),
    )
    if event is None:
        return {"status": "duplicate"}
    try:
        provider_config_keys = nango_provider_config_keys()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=503, detail="Integration configuration is invalid"
        ) from exc
    event.status = await apply_auth_webhook(
        db, payload, provider_config_keys=provider_config_keys
    )
    await db.commit()
    return {"status": event.status}
