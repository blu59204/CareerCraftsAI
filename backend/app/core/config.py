from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_SECRET_KEY: str
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str

    REDIS_URL: str = "redis://localhost:6379"
    REDIS_PASSWORD: str | None = None
    INTERNAL_SECRET: str | None = None
    # Internal URL agents use to reach the LLM gateway proxy. Override in
    # containerized deploys (e.g. http://backend:8000/llm-gateway/v1).
    LLM_GATEWAY_URL: str = "http://localhost:8000/llm-gateway/v1"
    RESEND_API_KEY: str = ""
    YOUTUBE_API_KEY: str = ""
    PROXYCURL_API_KEY: str = ""
    EXA_API_KEY: str | None = None
    AGENTQL_API_KEY: str | None = None
    SEARXNG_URL: str | None = None
    FIRECRAWL_API_KEY: str | None = None
    # JSearch (RapidAPI) — aggregates Google for Jobs / LinkedIn / Indeed / Naukri.
    RAPIDAPI_KEY: str | None = None
    # Adzuna (free key) — strong India + general coverage.
    ADZUNA_APP_ID: str | None = None
    ADZUNA_APP_KEY: str | None = None
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: str | None = None

    @model_validator(mode="after")
    def add_redis_password_to_url(self) -> "Settings":
        if (
            self.REDIS_PASSWORD
            and self.REDIS_URL.startswith("redis://")
            and "@" not in self.REDIS_URL.split("redis://", 1)[1].split("/", 1)[0]
        ):
            self.REDIS_URL = self.REDIS_URL.replace(
                "redis://", f"redis://:{self.REDIS_PASSWORD}@", 1
            )
        return self


settings = Settings()
