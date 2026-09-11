from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — single source of truth for all env vars.

    Required vars cause a clear Pydantic ValidationError at startup if missing.
    Optional vars have safe defaults so the app starts without them.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Required — app exits with clear error if any are missing ────────
    APP_SECRET_KEY: str
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_JWT_SECRET: str
    NEXT_PUBLIC_SUPABASE_URL: str = ""
    NEXT_PUBLIC_SUPABASE_ANON_KEY: str = ""
    REDIS_URL: str

    # ── Clerk Auth (primary identity provider) ─────────────────────────
    # Clerk signs session tokens with RS256. Either point CLERK_JWKS_URL at the
    # instance JWKS endpoint directly, or set CLERK_ISSUER and let the JWKS URL
    # be derived as "{issuer}/.well-known/jwks.json".
    #   CLERK_ISSUER   e.g. https://clean-mudfish-42.clerk.accounts.dev
    #   CLERK_JWKS_URL e.g. https://clean-mudfish-42.clerk.accounts.dev/.well-known/jwks.json
    # CLERK_SECRET_KEY is only needed for Backend API calls (user lookups), not
    # for token verification.
    CLERK_JWKS_URL: str = ""
    CLERK_ISSUER: str = ""
    CLERK_SECRET_KEY: str = ""
    # Clerk session tokens carry no fixed `aud` by default. Set this only if the
    # instance is configured to emit one — when empty, audience is not checked.
    CLERK_AUDIENCE: str = ""

    # ── App environment ────────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    FRONTEND_URL: str = "http://localhost:3000"

    # ── CORS ───────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    # ── Next.js public URLs ────────────────────────────────────────────
    NEXT_PUBLIC_APP_URL: str = "http://localhost:3000"
    NEXT_PUBLIC_API_URL: str = "http://localhost:8000"

    # ── Redis ──────────────────────────────────────────────────────────
    REDIS_PASSWORD: str | None = None

    # ── Internal / gateway ─────────────────────────────────────────────
    INTERNAL_SECRET: str = ""
    BACKEND_INTERNAL_URL: str = "http://backend:8000"
    LLM_GATEWAY_URL: str = "http://localhost:8000/llm-gateway/v1"

    # ── Browser Use ────────────────────────────────────────────────────
    # Controller LLM — use a local Ollama model for cost-efficient navigation
    # steps. Set BROWSER_USE_OLLAMA_URL to your Ollama instance; leave empty
    # to fall back to the user's configured BYOK model.
    BROWSER_USE_OLLAMA_MODEL: str = "llama3.2"
    BROWSER_USE_OLLAMA_URL: str = ""   # e.g. "http://localhost:11434"
    # Session limits — cap concurrent Chromium sessions to avoid OOM.
    # Rule of thumb: floor(VPS_RAM_GB * 1.5); e.g. 4GB VPS → 6, 2GB VPS → 3.
    BROWSER_USE_MAX_CONCURRENT_SESSIONS: int = 4
    BROWSER_USE_SESSION_MEM_LIMIT_MB: int = 500
    # Debug screenshots — save a PNG on every browser task failure.
    # Mount BROWSER_DEBUG_DIR as a Docker volume for persistence.
    BROWSER_DEBUG_SCREENSHOTS: bool = False
    BROWSER_DEBUG_DIR: str = "/tmp/browser_debug"  # noqa: S108
    # Human-like delay ranges per action type (milliseconds).
    # Lowering these increases detection risk; raising them slows runs.
    BROWSER_DELAY_NAVIGATE_MIN_MS: int = 1500   # page navigation
    BROWSER_DELAY_NAVIGATE_MAX_MS: int = 3500
    BROWSER_DELAY_FILL_MIN_MS: int = 300         # form field fill
    BROWSER_DELAY_FILL_MAX_MS: int = 800
    BROWSER_DELAY_CLICK_MIN_MS: int = 200        # button / link click
    BROWSER_DELAY_CLICK_MAX_MS: int = 600
    BROWSER_DELAY_EXTRACT_MIN_MS: int = 500      # wait after page load for extraction
    BROWSER_DELAY_EXTRACT_MAX_MS: int = 1500

    # ── External API keys (all optional) ───────────────────────────────
    HUNTER_API_KEY: str = ""
    PROXYCURL_API_KEY: str = ""
    EXA_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    YOUTUBE_API_KEY: str = ""
    AGENTQL_API_KEY: str | None = None
    FIRECRAWL_API_KEY: str | None = None
    SEARXNG_URL: str | None = None
    RAPIDAPI_KEY: str | None = None
    ADZUNA_APP_ID: str | None = None
    ADZUNA_APP_KEY: str | None = None
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: str | None = None

    # ── Search providers ───────────────────────────────────────────────
    TAVILY_API_KEY: str | None = None
    BRAVE_API_KEY: str | None = None
    SERPAPI_API_KEY: str | None = None
    BING_SEARCH_API_KEY: str | None = None
    GOOGLE_CSE_API_KEY: str | None = None
    GOOGLE_CSE_ID: str | None = None
    DUCKDUCKGO_ENABLED: bool = True
    MOJEEK_ENABLED: bool = True

    # ── Agent configuration ────────────────────────────────────────────
    AGENT_DEFAULT_TIMEOUT_S: int = 60
    AGENT_MAX_CONCURRENT_PER_USER: int = 2
    AGENT_THINKING_BUDGET_TOKENS: int = 8000
    WORKFLOW_WORKER_CONCURRENCY: int = Field(default=2, ge=1, le=32)
    WORKFLOW_QUEUE: str = "workflow-queue"
    WORKFLOW_DISPATCH_INTERVAL_S: int = Field(default=3, ge=1, le=60)
    WORKFLOW_TASK_TIMEOUT_S: int = Field(default=300, ge=30, le=1800)

    # OpenSandbox runs on dedicated infrastructure, never in the API process.
    OPEN_SANDBOX_URL: str = ""
    OPEN_SANDBOX_API_KEY: str = ""
    OPEN_SANDBOX_CHROME_IMAGE: str = "careercraft-browser:1"
    SANDBOX_TTL_SECONDS: int = Field(default=1800, ge=600, le=7200)
    SANDBOX_MAX_ACTIVE: int = Field(default=4, ge=1, le=1000)
    SANDBOX_CPU: str = "1000m"
    SANDBOX_MEMORY: str = "1024Mi"
    # Explicit domain allowlist, including identity/CDN domains for supported portals.
    SANDBOX_ALLOWED_DOMAINS: str = ""

    # ── RAG configuration ──────────────────────────────────────────────
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 5

    # ── Rate limiting ──────────────────────────────────────────────────
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_AGENT_RUN: str = "10/minute"
    RATE_LIMIT_UPLOAD: str = "5/minute"
    RATE_LIMIT_STR: str = "100/minute"

    # ── Supabase Storage ───────────────────────────────────────────────
    SUPABASE_STORAGE_BUCKET: str = "documents"

    # ── Document storage ───────────────────────────────────────────────
    # Uploaded resumes/documents live on local disk. Supabase Storage is
    # unreachable from the deployment VM for the same reason the managed
    # database was (its hosts resolve IPv6-only and the VM has no IPv6).
    # In Docker this is a named volume shared by backend and agent-worker;
    # back it up, because unlike the old bucket nothing else holds a copy.
    DOCUMENT_STORAGE_DIR: str = "/data/documents"

    @model_validator(mode="after")
    def _inject_redis_password(self) -> "Settings":
        if (
            self.REDIS_PASSWORD
            and self.REDIS_URL.startswith("redis://")
            and "@" not in self.REDIS_URL.split("redis://", 1)[1].split("/", 1)[0]
        ):
            self.REDIS_URL = self.REDIS_URL.replace(
                "redis://", f"redis://:{self.REDIS_PASSWORD}@", 1
            )
        return self

    @property
    def REDIS_URL_SAFE(self) -> str:
        import re
        url = self.REDIS_URL
        return re.sub(r"://.*@", "://***@", url)


settings = Settings()
