"""
llm_gateway.py — Internal LLM Gateway (proxy pattern).

Agents call this gateway with a session token instead of a real API key.
The gateway injects the real API key at the HTTP transport layer.

Even if an agent is fully compromised via prompt injection, it cannot
extract the API key because the key never exists in the agent's context.

Architecture:
    Agent → ChatOpenAI(base_url="http://localhost:8001/v1", api_key=session_token)
         → LLM Gateway (this service)
         → Injects real API key
         → Forwards to actual provider (OpenAI, Anthropic, etc.)

Usage:
    from app.core.llm_gateway import get_gateway_llm
    llm = await get_gateway_llm(user_id, db)
    # llm has NO access to the real API key — only a session token
"""
import hashlib
import hmac
import logging
import time
from typing import Any

from fastapi import APIRouter, Request, Response, HTTPException
import httpx

from app.core.config import settings
from app.core.security import decrypt_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm-gateway", tags=["llm-gateway"])

# Session token → (user_id, provider, model_name, expires_at)
_active_sessions: dict[str, dict[str, Any]] = {}

# Provider base URLs
_PROVIDER_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "nvidia_nim": "https://integrate.api.nvidia.com/v1",
}


def _generate_session_token(user_id: str, provider: str) -> str:
    """Generate a short-lived session token for gateway auth."""
    payload = f"{user_id}:{provider}:{int(time.time())}"
    return hmac.HMAC(
        settings.APP_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()[:48]


async def create_gateway_session(user_id: str, model_settings) -> dict:
    """Create a gateway session for a user. Returns session token + gateway URL.

    The session token is NOT the API key — it's a temporary credential
    that the gateway uses to look up the real key at request time.
    """
    token = _generate_session_token(user_id, model_settings.provider)

    _active_sessions[token] = {
        "user_id": user_id,
        "provider": model_settings.provider,
        "model_name": model_settings.model_name,
        "api_key_enc": model_settings.api_key_enc,
        "created_at": time.time(),
        "expires_at": time.time() + 3600,  # 1 hour TTL
    }

    return {
        "token": token,
        "gateway_url": f"http://localhost:8000/llm-gateway/v1",
        "model": model_settings.model_name,
    }


def _get_session(token: str) -> dict | None:
    """Validate and return session data. Returns None if expired/invalid."""
    session = _active_sessions.get(token)
    if not session:
        return None
    if time.time() > session["expires_at"]:
        del _active_sessions[token]
        return None
    return session


@router.api_route("/v1/{path:path}", methods=["POST", "GET"])
async def proxy_llm_request(path: str, request: Request) -> Response:
    """Proxy LLM requests — inject real API key at transport layer.

    The agent sends requests here with a session token as the "api_key".
    We strip it, look up the real key, and forward to the actual provider.
    """
    # Extract session token from Authorization header
    auth = request.headers.get("authorization", "")
    token = auth.replace("Bearer ", "").strip()

    session = _get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired gateway session")

    # Decrypt the real API key
    real_key = decrypt_api_key(session["api_key_enc"], settings.APP_SECRET_KEY)
    provider = session["provider"]
    provider_url = _PROVIDER_URLS.get(provider)

    if not provider_url:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Build forwarded request with real credentials
    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    if provider == "anthropic":
        headers["x-api-key"] = real_key
        headers["anthropic-version"] = "2023-06-01"
        headers.pop("authorization", None)
    else:
        headers["authorization"] = f"Bearer {real_key}"

    target_url = f"{provider_url}/{path}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.request(
            method=request.method,
            url=target_url,
            content=body,
            headers=headers,
        )

    # Strip any key echoes from response (defense in depth)
    from app.services.llm_proxy_service import redact_keys
    response_body = redact_keys(resp.text)

    return Response(
        content=response_body.encode(),
        status_code=resp.status_code,
        headers={"content-type": resp.headers.get("content-type", "application/json")},
    )


async def get_gateway_llm(user_id: str, db):
    """Build an LLM instance that routes through the gateway (key-free).

    The returned LLM uses the gateway URL as base_url and a session token
    as the api_key. The real API key never enters the agent's memory.
    """
    from langchain_openai import ChatOpenAI
    from sqlalchemy import select
    from app.models.db import UserModelSettings

    result = await db.execute(
        select(UserModelSettings).where(
            UserModelSettings.user_id == user_id,
            UserModelSettings.is_active == True,  # noqa: E712
        )
    )
    model_settings = result.scalars().first()
    if not model_settings:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No active model configured.")

    session = await create_gateway_session(user_id, model_settings)

    # All providers get an OpenAI-compatible interface via the gateway
    return ChatOpenAI(
        model=session["model"],
        api_key=session["token"],  # NOT the real key — just a session token
        base_url=session["gateway_url"],
    )
