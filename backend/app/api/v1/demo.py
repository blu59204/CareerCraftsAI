"""Public, unauthenticated job search for the marketing site's demo section.

Hits only the free key-less job-board APIs (Remotive/Arbeitnow/Jobicy) via
``search_all_platforms(platforms=["open_apis"])`` — no LLM call, no browser
automation — so every result is a real, live listing and the endpoint is
cheap enough to expose to anonymous visitors. Capped at
``MAX_DEMO_SEARCHES_PER_IP`` lifetime searches per IP address (tracked in
Redis, independent of process restarts or multiple backend replicas) so it
can't be used as a free unauthenticated scraping proxy.
"""

from __future__ import annotations

import hashlib
import logging
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from slowapi.util import get_remote_address

from app.core.rate_limit import limiter
from app.core.redis_client import get_redis
from app.services.job_search_service import search_all_platforms

router = APIRouter(prefix="/demo", tags=["demo"])
logger = logging.getLogger(__name__)

MAX_DEMO_SEARCHES_PER_IP = 2
# Bounds Redis storage growth; functionally still "twice, period" for any
# realistic demo-visitor return window.
DEMO_COUNTER_TTL_SECONDS = 30 * 24 * 60 * 60
DEMO_MAX_RESULTS = 5
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class DemoJobSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=100)
    location: str = Field(default="Remote", max_length=100)

    @field_validator("query", "location")
    @classmethod
    def _sanitize(cls, v: str) -> str:
        return _CONTROL_CHARS.sub("", v.replace("\x00", "")).strip()


class DemoJob(BaseModel):
    title: str
    company: str
    location: str
    url: str
    platform: str


class DemoJobSearchResponse(BaseModel):
    jobs: list[DemoJob]
    searches_used: int
    searches_remaining: int


class DemoQuotaResponse(BaseModel):
    searches_used: int
    searches_remaining: int
    limit: int = MAX_DEMO_SEARCHES_PER_IP


def _demo_ip_key(request: Request) -> str:
    ip = get_remote_address(request)
    digest = hashlib.sha256(ip.encode()).hexdigest()[:24]
    return f"demo:job_search:count:{digest}"


@router.get("/job-search/quota", response_model=DemoQuotaResponse)
async def get_demo_quota(request: Request):
    """Read-only: lets the UI show remaining free searches before submit."""
    redis = get_redis()
    raw = await redis.get(_demo_ip_key(request))
    used = min(int(raw), MAX_DEMO_SEARCHES_PER_IP) if raw else 0
    return DemoQuotaResponse(
        searches_used=used,
        searches_remaining=max(0, MAX_DEMO_SEARCHES_PER_IP - used),
    )


@router.post("/job-search", response_model=DemoJobSearchResponse)
@limiter.limit("10/minute")
async def demo_job_search(request: Request, payload: DemoJobSearchRequest):
    redis = get_redis()
    key = _demo_ip_key(request)

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, DEMO_COUNTER_TTL_SECONDS)

    if count > MAX_DEMO_SEARCHES_PER_IP:
        raise HTTPException(
            status_code=429,
            detail=(
                f"You've used your {MAX_DEMO_SEARCHES_PER_IP} free demo searches. "
                "Sign up free to search without limits."
            ),
        )

    jobs, warnings = await search_all_platforms(
        {
            "search_query": payload.query,
            "location": payload.location,
            "max_results": DEMO_MAX_RESULTS,
        },
        platforms=["open_apis"],
        timeout_s=20,
    )
    if warnings:
        logger.info("Demo job search warnings for query %r: %s", payload.query, warnings)

    return DemoJobSearchResponse(
        jobs=[
            DemoJob(
                title=j.get("title", ""),
                company=j.get("company", ""),
                location=j.get("location", ""),
                url=j.get("url", ""),
                platform=j.get("platform", ""),
            )
            for j in jobs[:DEMO_MAX_RESULTS]
        ],
        searches_used=count,
        searches_remaining=max(0, MAX_DEMO_SEARCHES_PER_IP - count),
    )
