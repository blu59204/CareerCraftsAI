"""Synchronous bridge for legacy callers using the provider-neutral gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from threading import Thread
from typing import Any
from uuid import UUID

from app.integrations.factory import build_integration_gateway
from app.integrations.schemas import IntegrationProxyResponse


def _run[T](coroutine: Coroutine[Any, Any, T]) -> T:
    """Run an async gateway call from sync agents, including event-loop callers."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    result: list[T] = []
    error: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(coroutine))
        except BaseException as exc:
            error.append(exc)

    thread = Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


def proxy_request(
    *,
    user_id: str,
    provider: str,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    json_data: dict | None = None,
    content: bytes | None = None,
) -> IntegrationProxyResponse:
    """Use Nango to proxy one provider request without exposing OAuth tokens."""

    async def request() -> IntegrationProxyResponse:
        gateway = build_integration_gateway()
        try:
            return await gateway.proxy_request(
                user_id=UUID(user_id),
                provider=provider,
                method=method,
                path=path,
                headers=headers,
                json_data=json_data,
                content=content,
            )
        finally:
            close = getattr(gateway, "aclose", None)
            if close is not None:
                await close()

    return _run(request())
