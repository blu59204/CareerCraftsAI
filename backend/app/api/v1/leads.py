import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models.db import Lead, User

router = APIRouter(prefix="/leads", tags=["leads"])
logger = logging.getLogger(__name__)

VALID_STATUSES = {"cold", "warm", "hot", "contacted", "replied", "closed"}


class LeadResponse(BaseModel):
    id: uuid.UUID
    name: str | None
    email: str | None
    company: str | None
    linkedin_url: str | None
    status: str
    last_contact: datetime | None
    notes: str | None

    model_config = {"from_attributes": True}


class LeadCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    linkedin_url: str | None = Field(default=None, max_length=500)
    status: str = "cold"
    notes: str | None = Field(default=None, max_length=5000)


class LeadStatusUpdate(BaseModel):
    status: str


@router.get("", response_model=list[LeadResponse])
@limiter.limit("30/minute")
async def list_leads(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Lead)
        .where(Lead.user_id == current_user.id)
        .order_by(Lead.last_contact.desc().nullslast(), Lead.id.desc())
        .limit(100)
    )
    return result.scalars().all()


@router.post("", response_model=LeadResponse, status_code=201)
@limiter.limit("20/minute")
async def create_lead(
    request: Request,
    payload: LeadCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {VALID_STATUSES}")
    lead = Lead(
        user_id=current_user.id,
        name=payload.name,
        email=payload.email,
        company=payload.company,
        linkedin_url=payload.linkedin_url,
        status=payload.status,
        notes=payload.notes,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.patch("/{lead_id}/status", response_model=LeadResponse)
@limiter.limit("30/minute")
async def update_lead_status(
    request: Request,
    lead_id: uuid.UUID,
    payload: LeadStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {VALID_STATUSES}")
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == current_user.id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.status = payload.status
    lead.last_contact = datetime.now(UTC)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.delete("/{lead_id}", status_code=204)
@limiter.limit("20/minute")
async def delete_lead(
    request: Request,
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.user_id == current_user.id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.delete(lead)
    await db.commit()
