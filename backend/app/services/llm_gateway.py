"""LLM Gateway — build BaseChatModel from user's stored model settings.

Agents call get_llm(user_id, db) to get a provider-specific LLM instance.
The API key is decrypted at request time and never logged or stored.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_api_key
from app.models.db import UserModelSettings

logger = logging.getLogger(__name__)

_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "google": "gemini-2.0-flash",
    "ollama": "gemma4:latest",
    "nvidia_nim": "meta/llama-3.1-70b-instruct",
    "openrouter": "openai/gpt-4o",
    "opencode": "claude-sonnet-4-20250514",
}


async def get_llm(user_id: str, db: AsyncSession):
    """Build a LangChain chat model for the user's active provider.

    Raises HTTPException(400) if no model is configured.
    The decrypted API key is injected into the model and immediately discarded.
    """
    result = await db.execute(
        select(UserModelSettings).where(
            UserModelSettings.user_id == user_id,
            UserModelSettings.is_active.is_(True),
        )
    )
    model_settings: UserModelSettings | None = result.scalars().first()
    if not model_settings:
        raise HTTPException(
            status_code=400,
            detail="No AI model configured. Go to Settings → AI Models.",
        )

    api_key = decrypt_api_key(model_settings.api_key_enc, settings.APP_SECRET_KEY)
    provider = (model_settings.provider or "").lower()
    model_name = model_settings.model_name or _DEFAULT_MODELS.get(provider, "")

    llm = None

    match provider:
        case "anthropic":
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model=model_name, api_key=api_key, timeout=30, max_retries=1)
        case "openai":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=model_name, api_key=api_key, timeout=30, max_retries=1)
        case "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, timeout=30, max_retries=1)
        case "ollama":
            from langchain_ollama import ChatOllama
            base = model_settings.ollama_url or "http://localhost:11434"
            llm = ChatOllama(model=model_name, base_url=base, timeout=30)
        case "nvidia_nim":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model_name, api_key=api_key,
                base_url="https://integrate.api.nvidia.com/v1",
                timeout=30, max_retries=1,
            )
        case "openrouter":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model_name, api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={"HTTP-Referer": "https://careercraftai.local", "X-Title": "CareerCraft AI"},
                timeout=30, max_retries=1,
            )
        case "opencode":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model_name, api_key=api_key,
                base_url="https://opencode.ai/zen/v1",
                timeout=30, max_retries=1,
            )
        case _:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    from app.services.llm_proxy_service import get_redaction_callback
    llm.callbacks = [get_redaction_callback()]
    return llm
