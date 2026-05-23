from fastapi import HTTPException
from langchain_core.language_models import BaseChatModel
from app.core.security import decrypt_api_key
from app.core.config import settings
from app.models.db import UserModelSettings


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
            raise HTTPException(status_code=400, detail=f"Unknown provider: {model_settings.provider}")


def get_llm(user_id: str, db) -> BaseChatModel:
    model_settings: UserModelSettings | None = (
        db.query(UserModelSettings)
        .filter_by(user_id=user_id, is_active=True)
        .first()
    )
    if not model_settings:
        raise HTTPException(status_code=400, detail="No active model configured. Add a model in Settings.")

    api_key = decrypt_api_key(model_settings.api_key_enc, settings.APP_SECRET_KEY)
    return _make_llm(model_settings, api_key)


def _build_llm(model_settings) -> BaseChatModel:
    """Build LLM directly from model_settings object (no DB lookup needed)."""
    api_key = decrypt_api_key(model_settings.api_key_enc, settings.APP_SECRET_KEY)
    return _make_llm(model_settings, api_key)
