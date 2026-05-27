from fastapi import HTTPException
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import LLMResult
from typing import Any

from app.core.config import settings
from app.core.security import decrypt_api_key
from app.models.db import UserModelSettings
from app.services.llm_proxy_service import get_redaction_callback


class TokenTrackingCallback(BaseCallbackHandler):
    """Tracks token usage per LLM call for budget enforcement."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Record token usage after each LLM call."""
        token_usage = response.llm_output.get("token_usage", {}) if response.llm_output else {}
        total = token_usage.get("total_tokens", 0)
        if total > 0:
            import asyncio
            from app.services.token_budget_service import consume_tokens
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(consume_tokens(self.user_id, total))
                else:
                    loop.run_until_complete(consume_tokens(self.user_id, total))
            except Exception:
                pass  # Non-blocking — don't fail the LLM call


def _make_llm(model_settings, api_key: str) -> BaseChatModel:
    match model_settings.provider:
        case "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(model=model_settings.model_name, api_key=api_key)
        case "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=model_settings.model_name, api_key=api_key)
        case "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(model=model_settings.model_name, google_api_key=api_key)
        case "ollama":
            from langchain_ollama import ChatOllama

            return ChatOllama(model=model_settings.model_name, base_url=model_settings.ollama_url)
        case "nvidia_nim":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model_settings.model_name,
                api_key=api_key,
                base_url="https://integrate.api.nvidia.com/v1",
            )
        case _:
            raise HTTPException(
                status_code=400, detail=f"Unknown provider: {model_settings.provider}"
            )


async def get_llm(user_id: str, db) -> BaseChatModel:
    from sqlalchemy import select
    from app.services.token_budget_service import check_budget

    # Check budget before building LLM
    remaining = await check_budget(user_id)
    if remaining <= 0:
        raise HTTPException(
            status_code=429,
            detail="Daily token budget exceeded. Resets at midnight UTC.",
        )

    result = await db.execute(
        select(UserModelSettings).where(
            UserModelSettings.user_id == user_id,
            UserModelSettings.is_active == True,  # noqa: E712
        )
    )
    model_settings: UserModelSettings | None = result.scalars().first()
    if not model_settings:
        raise HTTPException(
            status_code=400, detail="No active model configured. Add a model in Settings."
        )

    api_key = decrypt_api_key(model_settings.api_key_enc, settings.APP_SECRET_KEY)
    llm = _make_llm(model_settings, api_key)
    llm.callbacks = [get_redaction_callback(), TokenTrackingCallback(user_id)]
    return llm


def _build_llm(model_settings) -> BaseChatModel:
    """Build LLM directly from model_settings object (no DB lookup needed)."""
    api_key = decrypt_api_key(model_settings.api_key_enc, settings.APP_SECRET_KEY)
    llm = _make_llm(model_settings, api_key)
    llm.callbacks = [get_redaction_callback()]
    return llm
