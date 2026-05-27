import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness import get_harness
from app.api.v1.deps import get_current_user, get_db
from app.models.db import AgentRun, SalaryReport, User

router = APIRouter(prefix="/salary", tags=["salary"])


class SalaryReportRequest(BaseModel):
    role: str
    company: str | None = None
    location: str | None = None
    offer_amount: int | None = None


@router.post("/report")
async def generate_salary_report(
    body: SalaryReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="salary_intelligence",
        status="running",
        input=body.model_dump(exclude_none=True),
    )
    db.add(agent_run)
    await db.flush()

    harness = await get_harness()
    await harness.run(
        user_id=str(current_user.id),
        task_type="salary_intelligence",
        context=body.model_dump(exclude_none=True),
        user_settings={},
        run_id=run_id,
    )
    return {"run_id": run_id, "status": "running"}


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
