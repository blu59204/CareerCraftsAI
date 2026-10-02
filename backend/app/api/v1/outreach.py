"""The member's recruiter outreach: review, approve, edit and cancel emails,
and see how they are doing."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models.db import RecruiterOutreach, User
from app.services import outreach_service

router = APIRouter(prefix="/outreach", tags=["outreach"])


class OutreachEdit(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    body: str | None = Field(default=None, min_length=1, max_length=8000)

    @field_validator("subject")
    @classmethod
    def _single_line(cls, value):
        if value is not None and ("\r" in value or "\n" in value):
            raise ValueError("Subject must be a single line")
        return value


def _item(row: RecruiterOutreach) -> dict:
    return {
        "id": str(row.id),
        "kind": row.kind,
        "company": row.company,
        "role": row.role,
        "to_email": row.to_email,
        "email_source": row.email_source,
        "verdict": row.verdict,
        "subject": row.subject,
        "body": row.body,
        "state": row.state,
        "resume_version": row.resume_version,
        "sent_at": row.sent_at,
        "replied_at": row.replied_at,
        "bounced_at": row.bounced_at,
        "opened_at": row.opened_at,
        "created_at": row.created_at,
    }


@router.get("")
async def list_outreach(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    rows = (
        (
            await db.execute(
                select(RecruiterOutreach)
                .where(RecruiterOutreach.user_id == current_user.id)
                .order_by(RecruiterOutreach.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [_item(row) for row in rows],
        "stats": await outreach_service.outreach_stats(db, current_user.id),
    }


# 1x1 transparent GIF
_PIXEL = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00"
    b"\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


@router.get("/open/{token}.gif", include_in_schema=False)
@limiter.limit("120/minute")
async def open_pixel(request: Request, token: str):
    """Tracking pixel for members who turned on open tracking. Public by
    design: the recipient's mail app loads it."""
    await outreach_service.record_open(token)
    return Response(
        content=_PIXEL,
        media_type="image/gif",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


def _parse_id(outreach_id: str) -> str:
    try:
        return str(uuid.UUID(outreach_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Email not found") from None


@router.post("/{outreach_id}/approve")
async def approve(outreach_id: str, current_user: User = Depends(get_current_user)):
    if not await outreach_service.approve_outreach(str(current_user.id), _parse_id(outreach_id)):
        raise HTTPException(status_code=409, detail="This email cannot be approved")
    return {"state": "approved"}


@router.post("/{outreach_id}/cancel")
async def cancel(outreach_id: str, current_user: User = Depends(get_current_user)):
    if not await outreach_service.cancel_outreach(str(current_user.id), _parse_id(outreach_id)):
        raise HTTPException(status_code=409, detail="This email cannot be cancelled")
    return {"state": "cancelled"}


@router.patch("/{outreach_id}")
async def edit(
    outreach_id: str, payload: OutreachEdit, current_user: User = Depends(get_current_user)
):
    if not await outreach_service.edit_outreach(
        str(current_user.id), _parse_id(outreach_id), payload.subject, payload.body
    ):
        raise HTTPException(status_code=409, detail="This email cannot be edited")
    return {"updated": True}
