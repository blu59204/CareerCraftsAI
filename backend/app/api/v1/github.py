from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.api.v1.deps import get_current_user
from app.core.rate_limit import limiter
from app.services import github_profile

router = APIRouter()


class PublicProfile(BaseModel):
    url: str = Field(min_length=1, max_length=200)


@router.get("/github/profile")
async def profile(user=Depends(get_current_user)):
    data = await github_profile.get_profile(user.id)
    if data is None:
        raise HTTPException(404, "GitHub is not connected")
    return data


@router.post("/github/public-profile")
@limiter.limit("5/hour")
async def public(request: Request, body: PublicProfile, user=Depends(get_current_user)):
    try:
        github_profile.public_login(body.url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        return await github_profile.refresh_profile(user.id, body.url)
    except Exception as exc:
        raise HTTPException(503, "GitHub unavailable or rate limited. Try again later.") from exc


@router.post("/github/refresh")
@limiter.limit("5/hour")
async def refresh(request: Request, user=Depends(get_current_user)):
    try:
        return await github_profile.refresh_profile(user.id)
    except LookupError as exc:
        raise HTTPException(404, "GitHub is not connected") from exc
    except Exception as exc:
        raise HTTPException(
            503, "GitHub unavailable or rate limited. You can use a public profile URL."
        ) from exc


@router.delete("/github/data", status_code=204)
async def delete_data(user=Depends(get_current_user)):
    await github_profile.delete_profile(user.id)
    return Response(status_code=204)
