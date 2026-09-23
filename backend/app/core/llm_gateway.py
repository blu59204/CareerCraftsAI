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
import json
import logging
import time

from fastapi import APIRouter, Request, Response, HTTPException
import httpx
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.security import decrypt_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm-gateway", tags=["llm-gateway"])

# Gateway sessions are stored in Redis (not in-process) so they are visible
# across all workers and expire automatically via TTL — no unbounded growth.
_SESSION_TTL_SECONDS = 3600
_SESSION_KEY_PREFIX = "llm_gw:session:"

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


# Internal base URL the agent uses to reach this gateway. Configurable so it
# works in containerized/multi-host deploys (not hardcoded to localhost).
_GATEWAY_BASE_URL = settings.LLM_GATEWAY_URL

# Provider base URLs
_PROVIDER_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "nvidia_nim": "https://integrate.api.nvidia.com/v1",
}


def _generate_session_token(user_id: str, provider: str) -> str:
    """Generate a unique short-lived session token for gateway auth.

    Includes a random nonce so two sessions for the same user/provider in the
    same second do not collide to the same token.
    """
    import secrets

    nonce = secrets.token_hex(8)
    payload = f"{user_id}:{provider}:{time.time()}:{nonce}"
    return hmac.HMAC(
        settings.APP_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()[:48]


async def create_gateway_session(user_id: str, model_settings) -> dict:
    """Create a gateway session for a user. Returns session token + gateway URL.

    The session token is NOT the API key — it's a temporary credential
    that the gateway uses to look up the real key at request time. Stored in
    Redis with a TTL so it is visible across workers and auto-expires.
    """
    token = _generate_session_token(user_id, model_settings.provider)

    session_data = {
        "user_id": user_id,
        "provider": model_settings.provider,
        "model_name": model_settings.model_name,
        "api_key_enc": model_settings.api_key_enc,
        "created_at": time.time(),
    }

    r = _get_redis()
    await r.setex(
        f"{_SESSION_KEY_PREFIX}{token}",
        _SESSION_TTL_SECONDS,
        json.dumps(session_data),
    )

    return {
        "token": token,
        "gateway_url": _GATEWAY_BASE_URL,
        "model": model_settings.model_name,
    }


async def _get_session(token: str) -> dict | None:
    """Validate and return session data from Redis. None if expired/invalid."""
    if not token:
        return None
    r = _get_redis()
    raw = await r.get(f"{_SESSION_KEY_PREFIX}{token}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


@router.post("/v1/{path:path}", operation_id="proxy_llm_request_post")
@router.get("/v1/{path:path}", operation_id="proxy_llm_request_get")
async def proxy_llm_request(path: str, request: Request) -> Response:
    """Proxy LLM requests — inject real API key at transport layer.

    The agent sends requests here with a session token as the "api_key".
    We strip it, look up the real key, and forward to the actual provider.
    """
    # Extract session token from Authorization header
    auth = request.headers.get("authorization", "")
    token = auth.replace("Bearer ", "").strip()

    session = await _get_session(token)
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
