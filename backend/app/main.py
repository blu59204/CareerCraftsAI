from __future__ import annotations

import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import internal
from app.api.v1 import (
    agents,
    browser,
    company,
    cover_letter,
    email,
    interview,
    interview_prep,
    jobs,
    leads,
    linkedin,
    rag,
    resume,
    salary,
    users,
)
from app.core.config import settings
from app.core.rate_limit import limiter
from memory.routes import router as memory_router

logger = logging.getLogger(__name__)

_REQUIRED_VARS = [
    "APP_SECRET_KEY",
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_JWT_SECRET",
    "REDIS_URL",
]


def _check_env_vars() -> None:
    missing = []
    for k in _REQUIRED_VARS:
        v = os.getenv(k)
        if not v or not v.strip():
            missing.append(k)
    if missing:
        logger.critical("Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)
    logger.info("All %d required env vars present", len(_REQUIRED_VARS))


def _build_cors_origins(raw: str, env: str) -> list[str]:
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if "*" in origins:
        raise ValueError("CORS_ORIGINS must not contain '*' — specify exact origins")
    if env != "production":
        for o in ("http://localhost:3000", "http://127.0.0.1:3000"):
            if o not in origins:
                origins.append(o)
    return origins


_cors_raw = settings.CORS_ORIGINS or settings.ALLOWED_ORIGINS or settings.FRONTEND_URL
_allowed_origins = _build_cors_origins(_cors_raw, settings.APP_ENV)

# ── Request ID middleware (uuid4) ────────────────────────────────
async def _request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


# ── JWT middleware (skip public paths) ───────────────────────────
_PUBLIC_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/internal"}

from app.core.supabase_auth import verify_token


async def _jwt_middleware(request: Request, call_next):
    path = request.url.path
    if path in _PUBLIC_PATHS or path.startswith("/internal"):
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing or invalid Authorization header"},
        )
    try:
        token = auth_header.split(" ", 1)[1]
        payload = verify_token(token)
        request.state.user = payload
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
        )
    return await call_next(request)


# ── Lifespan ─────────────────────────────────────────────────────
@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _check_env_vars()

    from app.core.database import check_db_connection
    from app.core.redis_client import check_redis_connection

    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()
    if not db_ok:
        logger.error("Database connection failed at startup")
    if not redis_ok:
        logger.error("Redis connection failed at startup")

    try:
        from app.core.database import engine
        async with engine.begin() as conn:
            from sqlalchemy import text
            result = await conn.execute(text(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ))
            row = result.fetchone()  # CursorResult.fetchone() is synchronous
            if row:
                logger.info("pgvector installed: version %s", row[0])
            else:
                logger.warning("pgvector extension not installed — run CREATE EXTENSION vector")
    except Exception as exc:
        logger.warning("pgvector check failed: %s", exc)

    logger.info("Startup complete — db=%s redis=%s", db_ok, redis_ok)

    # Warm up the SSE publisher thread at startup so the first emit() never drops
    try:
        from app.core.event_bus import _ensure_publisher
        _ensure_publisher()
        logger.info("SSE publisher thread ready")
    except Exception as exc:
        logger.warning("SSE publisher warmup failed: %s", exc)

    yield
    logger.info("Shutting down")
    from app.core.redis_client import close_redis
    await close_redis()
    from app.core.database import engine
    await engine.dispose()


# ── App factory ──────────────────────────────────────────────────
app = FastAPI(
    title="CareerCraft AI API",
    version="1.0.0",
    lifespan=_lifespan,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
    openapi_url="/openapi.json" if settings.APP_ENV != "production" else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def _generic_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Starlette builds the stack so the LAST-registered middleware is OUTERMOST.
# CORS must therefore be registered last: a 401 returned by _jwt_middleware has
# to travel back out through CORSMiddleware to pick up Access-Control-Allow-Origin,
# otherwise the browser reports an opaque CORS failure and the frontend can't tell
# an expired token from a dead network.
# Execution order: CORS → request ID → JWT → route.
app.middleware("http")(_jwt_middleware)
app.middleware("http")(_request_id_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# Routers
app.include_router(users.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")
app.include_router(resume.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(leads.router, prefix="/api/v1")
app.include_router(email.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(browser.router, prefix="/api/v1")
app.include_router(interview_prep.router, prefix="/api/v1")
app.include_router(cover_letter.router, prefix="/api/v1")
app.include_router(interview.router, prefix="/api/v1")
app.include_router(salary.router, prefix="/api/v1")
app.include_router(company.router, prefix="/api/v1")
app.include_router(linkedin.router, prefix="/api/v1")
app.include_router(memory_router)
app.include_router(internal.router)

from app.core.llm_gateway import router as llm_gw
app.include_router(llm_gw)


# ── Health endpoint (no auth required) ──────────────────────────
@app.get("/health")
async def health():
    from fastapi.responses import JSONResponse

    from app.core.database import check_db_connection
    from app.core.redis_client import check_redis_connection
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()
    pgvector_ok = False
    try:
        from app.core.database import engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            pgvector_ok = result.fetchone() is not None
    except Exception:
        pgvector_ok = False
    all_ok = bool(db_ok and redis_ok and pgvector_ok)
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "ok" if all_ok else "error",
            "version": app.version,
            "db": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
            "pgvector": "ok" if pgvector_ok else "error",
        },
    )
