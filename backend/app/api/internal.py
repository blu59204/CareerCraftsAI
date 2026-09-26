"""Operator-only endpoints, protected by INTERNAL_SECRET (never a user JWT)
and blocked at nginx. Temporal runs these jobs on its own; the endpoints
exist to trigger one by hand when debugging.
"""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.config import settings
from app.services import scheduled_jobs
from app.services.scheduled_jobs import FollowupTrigger, JobSearchTrigger, StatusCheckTrigger

router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_secret(x_internal_secret: str = Header(...)) -> None:
    # Fail closed: no fallback to APP_SECRET_KEY (that value also encrypts
    # every stored provider credential, so it must never double as a
    # network-facing bearer token), and an unset INTERNAL_SECRET must not
    # match an empty header — hmac.compare_digest("", "") is True.
    internal_secret = settings.INTERNAL_SECRET
    if not internal_secret or not hmac.compare_digest(x_internal_secret, internal_secret):
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/health", dependencies=[Depends(_verify_secret)])
async def internal_health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/agents/run-job-search", dependencies=[Depends(_verify_secret)])
async def run_job_search(payload: JobSearchTrigger):
    return await scheduled_jobs.run_job_search(payload)


@router.post("/agents/run-followup", dependencies=[Depends(_verify_secret)])
async def run_followup(payload: FollowupTrigger):
    return await scheduled_jobs.run_followup(payload)


@router.post("/agents/daily-search", dependencies=[Depends(_verify_secret)])
async def daily_search(payload: StatusCheckTrigger):
    return await scheduled_jobs.daily_search(payload)


@router.post("/applications/check-status", dependencies=[Depends(_verify_secret)])
async def check_application_status(payload: StatusCheckTrigger):
    return await scheduled_jobs.check_application_status(payload)
