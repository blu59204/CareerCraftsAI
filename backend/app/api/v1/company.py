from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.models.db import CompanyIntelModel, User

router = APIRouter(prefix="/company", tags=["company"])


class CompanyResearchRequest(BaseModel):
    company_name: str


@router.get("/{name}/intel")
async def get_company_intel(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CompanyIntelModel).where(
            CompanyIntelModel.company_name == name,
            CompanyIntelModel.user_id == current_user.id,
        )
    )
    intel = result.scalar_one_or_none()
    if not intel:
        raise HTTPException(status_code=404, detail="Company intel not found")
    return intel
