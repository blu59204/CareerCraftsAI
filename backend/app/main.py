import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import internal
from app.api.v1 import agents, company, cover_letter, email, interview, interview_prep, jobs, leads, linkedin, rag, resume, salary, users
from app.core.config import settings
from app.core.rate_limit import limiter
from memory.routes import router as memory_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="JobAgent AI API",
    version="0.1.0",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
    openapi_url="/openapi.json" if settings.APP_ENV != "production" else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

_raw_origins = getattr(settings, "ALLOWED_ORIGINS", settings.FRONTEND_URL)
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
if "*" in _allowed_origins:
    raise ValueError(
        "ALLOWED_ORIGINS contains '*' which is not permitted. "
        "Set specific origins in your .env file, e.g. ALLOWED_ORIGINS=http://localhost:3000"
    )

# Always include both 3000 and 3001 in dev so the port Next.js picks doesn't matter
if settings.APP_ENV != "production":
    for _p in ("http://localhost:3000", "http://localhost:3001"):
        if _p not in _allowed_origins:
            _allowed_origins.append(_p)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.include_router(users.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")
app.include_router(resume.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(leads.router, prefix="/api/v1")
app.include_router(email.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(interview_prep.router, prefix="/api/v1")
app.include_router(cover_letter.router, prefix="/api/v1")
app.include_router(interview.router, prefix="/api/v1")
app.include_router(salary.router, prefix="/api/v1")
app.include_router(company.router, prefix="/api/v1")
app.include_router(linkedin.router, prefix="/api/v1")
app.include_router(memory_router)
app.include_router(internal.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
