import logging

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.api.v1.deps import get_current_user
from app.core.rate_limit import limiter
from app.models.db import User

router = APIRouter(prefix="/interview-prep", tags=["interview-prep"])
logger = logging.getLogger(__name__)


class VideoResult(BaseModel):
    video_id: str
    title: str
    channel: str
    thumbnail: str
    embed_url: str
    watch_url: str
    description: str


@router.get("/videos", response_model=list[VideoResult])
@limiter.limit("30/minute")
async def get_interview_videos(
    request: Request,
    company: str = Query(default="", max_length=200),
    role: str = Query(default="software engineer", max_length=200),
    current_user: User = Depends(get_current_user),
):
    from app.services.youtube_service import search_interview_videos

    videos = await search_interview_videos(company=company, role=role)
    return [VideoResult(**v) for v in videos]
