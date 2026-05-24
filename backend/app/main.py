from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import internal
from app.api.v1 import agents, email, jobs, leads, rag, resume, users
from app.core.config import settings
from app.core.rate_limit import limiter
from memory.routes import router as memory_router

app = FastAPI(
    title="JobAgent AI API",
    version="0.1.0",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.FRONTEND_URL == "*":
    raise RuntimeError("FRONTEND_URL cannot be '*' — set a specific origin in .env")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
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
app.include_router(memory_router)
app.include_router(internal.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
