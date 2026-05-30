import logging
from typing import Any

from fastapi import HTTPException
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import LLMResult

from app.core.config import settings
from app.core.security import decrypt_api_key
from app.models.db import UserModelSettings
from app.services.llm_proxy_service import get_redaction_callback

logger = logging.getLogger(__name__)
LLM_TIMEOUT_SECONDS = 30
LLM_MAX_RETRIES = 1


class TokenTrackingCallback(BaseCallbackHandler):
    """Tracks token usage per LLM call for budget enforcement."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Record token usage after each LLM call."""
        token_usage = response.llm_output.get("token_usage", {}) if response.llm_output else {}
        total = token_usage.get("total_tokens", 0)
        if total > 0:
            from app.services.token_budget_service import consume_tokens
            from app.core.sync_db import run_coro_sync
            try:
                # This callback runs inside a sync LLM call on a worker thread,
                # so there is no running loop here; run_coro_sync executes the
                # async decrement to completion. (The previous get_event_loop()
                # path silently no-op'd, so budgets never decremented.)
                run_coro_sync(consume_tokens(self.user_id, total))
            except Exception as exc:
                logger.debug("Token budget tracking failed for user %s: %s", self.user_id, exc)


def _make_llm(model_settings, api_key: str) -> BaseChatModel:
    match model_settings.provider:
        case "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=model_settings.model_name,
                api_key=api_key,
                timeout=LLM_TIMEOUT_SECONDS,
                max_retries=LLM_MAX_RETRIES,
            )
        case "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model_settings.model_name,
                api_key=api_key,
                timeout=LLM_TIMEOUT_SECONDS,
                max_retries=LLM_MAX_RETRIES,
            )
        case "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=model_settings.model_name,
                google_api_key=api_key,
                timeout=LLM_TIMEOUT_SECONDS,
                max_retries=LLM_MAX_RETRIES,
            )
        case "ollama":
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=model_settings.model_name,
                base_url=model_settings.ollama_url,
                timeout=LLM_TIMEOUT_SECONDS,
            )
        case "nvidia_nim":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model_settings.model_name,
                api_key=api_key,
                base_url="https://integrate.api.nvidia.com/v1",
                timeout=LLM_TIMEOUT_SECONDS,
                max_retries=LLM_MAX_RETRIES,
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
    callbacks = [get_redaction_callback()]
    user_id = getattr(model_settings, "user_id", None)
    if user_id:
        callbacks.append(TokenTrackingCallback(str(user_id)))
    llm.callbacks = callbacks
    return llm
