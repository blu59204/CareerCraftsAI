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

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Request, Response

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
        "ollama_url": model_settings.ollama_url,
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
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""

    session = await _get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired gateway session")

    # Native provider adapters belong at the credential boundary. Reuse the
    # configured adapters rather than pretending every provider speaks OpenAI.
    if request.method != "POST" or path != "chat/completions":
        raise HTTPException(status_code=404, detail="Unsupported gateway operation")
    from types import SimpleNamespace

    from langchain_core.messages import convert_to_messages
    from pydantic import BaseModel, Field, ValidationError

    from app.agents.prompts import with_security_rules
    from app.core.model_router import _make_llm
    from app.services.llm_proxy_service import get_redaction_callback, redact_keys

    class ChatRequest(BaseModel):
        model: str = Field(min_length=1, max_length=200)
        messages: list[dict] = Field(min_length=1, max_length=100)
        stream: bool = False

    try:
        body = await request.body()
        if len(body) > 250000:
            raise HTTPException(status_code=413, detail="Chat input is too large")
        raw = json.loads(body)
        if not isinstance(raw, dict):
            raise ValueError("Expected object")
        if any(raw.get(field) for field in ("tools", "functions", "response_format")):
            raise HTTPException(status_code=422, detail="Unsupported chat operation")
        payload = ChatRequest.model_validate(raw)
        if any(
            message.get("role") not in ("system", "user", "assistant")
            or not isinstance(message.get("content"), str)
            for message in payload.messages
        ):
            raise ValueError("Only text messages are supported")
        # Every agent's calls pass here, so this is where the shared
        # untrusted-content rules are guaranteed, inline prompts included.
        messages = with_security_rules(convert_to_messages(payload.messages))
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Invalid chat request") from None
    if payload.model != session["model_name"]:
        raise HTTPException(status_code=403, detail="Model does not match gateway session")
    if payload.stream:
        raise HTTPException(status_code=422, detail="Streaming is unavailable on this gateway")
    if sum(len(str(message.content)) for message in messages) > 200000:
        raise HTTPException(status_code=413, detail="Chat input is too large")
    key = (
        decrypt_api_key(session["api_key_enc"], settings.APP_SECRET_KEY)
        if session.get("api_key_enc")
        else ""
    )
    model_settings = SimpleNamespace(
        provider=session["provider"],
        model_name=session["model_name"],
        ollama_url=session.get("ollama_url"),
    )
    try:
        llm = _make_llm(model_settings, key)
        llm.callbacks = [get_redaction_callback()]
        result = await llm.ainvoke(messages)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "gateway_provider_failed provider=%s error_type=%s",
            session["provider"],
            type(exc).__name__,
        )
        raise HTTPException(status_code=502, detail="Model provider request failed") from None
    content = result.content
    if isinstance(content, list):
        content = "".join(block.get("text", "") for block in content if isinstance(block, dict))
    usage = result.usage_metadata or {}
    response = {
        "id": "chatcmpl-" + _generate_session_token(session["user_id"], session["provider"]),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": session["model_name"],
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }
    return Response(content=redact_keys(json.dumps(response)), media_type="application/json")


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

    from app.services.token_budget_service import check_budget

    if await check_budget(user_id) <= 0:
        raise HTTPException(status_code=429, detail="Daily token budget exceeded.")
    session = await create_gateway_session(user_id, model_settings)

    # All providers get an OpenAI-compatible interface via the gateway
    return ChatOpenAI(
        model=session["model"],
        api_key=session["token"],  # NOT the real key — just a session token
        base_url=session["gateway_url"],
        timeout=120,
        max_retries=0,
    )


def build_gateway_llm(model_settings, user_id: str):
    """Sync node entry point: only a temporary gateway credential reaches agents."""
    import redis
    from langchain_openai import ChatOpenAI

    from app.core.model_router import TokenTrackingCallback, _check_budget_sync
    from app.services.llm_proxy_service import get_redaction_callback

    _check_budget_sync(user_id)
    token = _generate_session_token(user_id, model_settings.provider)
    data = {
        "user_id": user_id,
        "provider": model_settings.provider,
        "model_name": model_settings.model_name,
        "api_key_enc": model_settings.api_key_enc,
        "ollama_url": model_settings.ollama_url,
        "created_at": time.time(),
    }
    with redis.from_url(settings.REDIS_URL, decode_responses=True) as client:
        client.setex(f"{_SESSION_KEY_PREFIX}{token}", _SESSION_TTL_SECONDS, json.dumps(data))
    return ChatOpenAI(
        model=model_settings.model_name,
        api_key=token,
        base_url=_GATEWAY_BASE_URL,
        timeout=120,
        max_retries=0,
        callbacks=[get_redaction_callback(), TokenTrackingCallback(user_id)],
    )
