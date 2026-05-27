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
    PINCHTAB_URL: str = "http://localhost:9867"
    PINCHTAB_TOKEN: str = ""
    RESEND_API_KEY: str = ""
    YOUTUBE_API_KEY: str = ""
    PROXYCURL_API_KEY: str = ""
    EXA_API_KEY: str | None = None
    FIRECRAWL_API_KEY: str | None = None


settings = Settings()
