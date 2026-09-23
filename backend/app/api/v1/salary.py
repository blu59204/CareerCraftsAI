import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness import get_harness
from app.api.v1.deps import get_current_user, get_db
from app.api.v1.run_utils import apply_harness_result
from app.models.db import AgentRun, SalaryReport, User

router = APIRouter(prefix="/salary", tags=["salary"])

HARNESS_TIMEOUT_SECONDS = 120


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
    try:
        harness_result = await asyncio.wait_for(
            harness.run(
                user_id=str(current_user.id),
                task_type="salary_intelligence",
                context=body.model_dump(exclude_none=True),
                user_settings={},
                run_id=run_id,
            ),
            timeout=HARNESS_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        agent_run.status = "failed"
        agent_run.output = {"error": f"Timed out after {HARNESS_TIMEOUT_SECONDS}s"}
        await db.flush()
        raise HTTPException(status_code=504, detail="Salary report generation timed out") from None

    output = apply_harness_result(agent_run, harness_result) or {}
    action = harness_result.get("pending_action") or {}
    report_data = action.get("report") if isinstance(action, dict) else None
    script = action.get("script") if isinstance(action, dict) else None
    if not report_data and isinstance(output, dict):
        report_data = output

    if isinstance(report_data, dict):
        existing = await db.get(SalaryReport, uuid.UUID(run_id))
        report = existing or SalaryReport(id=uuid.UUID(run_id), user_id=current_user.id)
        report.role = report_data.get("role") or body.role
        report.company = report_data.get("company") or body.company
        report.location = report_data.get("location") or body.location or ""
        report.p25 = int(report_data.get("p25") or 0)
        report.p50 = int(report_data.get("p50") or 0)
        report.p75 = int(report_data.get("p75") or 0)
        report.offer_amount = report_data.get("offer_amount") or body.offer_amount
        report.classification = report_data.get("classification")
        report.negotiation_script = script
        report.data_sources = report_data.get("data_sources") or []
        report.data_unavailable = bool(report_data.get("data_unavailable"))
        if existing is None:
            db.add(report)

    await db.flush()
    return {"run_id": run_id, "status": agent_run.status}


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
