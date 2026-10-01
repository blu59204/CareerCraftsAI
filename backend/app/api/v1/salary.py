import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.models.db import SalaryReport, User

router = APIRouter(prefix="/salary", tags=["salary"])


class SalaryReportRequest(BaseModel):
    role: str
    company: str | None = None
    location: str | None = None
    offer_amount: int | None = None


@router.get("/report/{report_id}")
async def get_salary_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SalaryReport).where(
            SalaryReport.id == report_id,
            SalaryReport.user_id == current_user.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
