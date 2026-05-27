import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness import get_harness
from app.api.v1.deps import get_current_user, get_db
from app.models.db import AgentRun, CompanyIntelModel, User

router = APIRouter(prefix="/company", tags=["company"])


class CompanyResearchRequest(BaseModel):
    company_name: str


@router.post("/research")
async def research_company(
    body: CompanyResearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="company_research",
        status="running",
        input={"company_name": body.company_name},
    )
    db.add(agent_run)
    await db.flush()

    harness = await get_harness()
    await harness.run(
        user_id=str(current_user.id),
        task_type="company_research",
        context={"company_name": body.company_name},
        user_settings={},
        run_id=run_id,
    )
    return {"run_id": run_id, "status": "running"}


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
