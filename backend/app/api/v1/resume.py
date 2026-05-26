import asyncio
import base64
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.resume_agent import resume_agent_node
from app.agents.state import AgentState
from app.api.v1.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models.db import AgentRun, User, UserDocument

router = APIRouter(prefix="/resume", tags=["resume"])
logger = logging.getLogger(__name__)


class OptimizeRequest(BaseModel):
    jd_text: str = Field(max_length=20000)
    template: str = Field(default="modern")


class OptimizeResponse(BaseModel):
    run_id: str
    status: str
    resume_text: str | None = None
    pdf_available: bool = False
    template: str = "modern"


class AtsScoreRequest(BaseModel):
    jd_text: str = Field(default="", max_length=20000)
    document_id: uuid.UUID | None = None


class AtsScoreResponse(BaseModel):
    composite_score: int
    keyword_score: int
    readability_score: int
    format_score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    suggestions: list[str]
    flesch_kincaid: float
    avg_sentence_length: float
    format_checks: dict[str, bool]


@router.post("/optimize", response_model=OptimizeResponse)
@limiter.limit("10/minute")
async def optimize_resume(
    request: Request,
    payload: OptimizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not payload.jd_text.strip():
        raise HTTPException(status_code=400, detail="jd_text cannot be empty")

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="resume",
        status="running",
        input={"jd_text": payload.jd_text[:500]},
    )
    db.add(agent_run)
    await db.flush()

    state = AgentState(
        user_id=str(current_user.id),
        run_id=run_id,
        task_type="resume_optimize",
        messages=[HumanMessage(content=payload.jd_text)],
        context={"jd_text": payload.jd_text, "template": payload.template},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )

    result_state = await asyncio.get_running_loop().run_in_executor(
        None, resume_agent_node, state
    )

    agent_run.status = result_state["status"]
    agent_run.completed_at = datetime.now(timezone.utc)
    if result_state.get("pending_action"):
        agent_run.output = {
            "type": result_state["pending_action"].get("type"),
            "pdf_b64": result_state["pending_action"].get("pdf_b64"),
        }

    if result_state["status"] == "failed":
        raise HTTPException(
            status_code=500, detail=result_state.get("error", "Agent failed")
        )

    pending = result_state.get("pending_action") or {}
    return OptimizeResponse(
        run_id=run_id,
        status=result_state["status"],
        resume_text=pending.get("resume_text"),
        pdf_available=bool(pending.get("pdf_b64")),
        template=payload.template,
    )


@router.get("/download/{run_id}")
async def download_pdf(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentRun).where(
            AgentRun.id == uuid.UUID(run_id),
            AgentRun.user_id == current_user.id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.output or "pdf_b64" not in run.output:
        raise HTTPException(status_code=404, detail="PDF not available for this run")

    pdf_bytes = base64.b64decode(run.output["pdf_b64"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=resume_{run_id[:8]}.pdf"
        },
    )


@router.post("/ats-score", response_model=AtsScoreResponse)
@limiter.limit("20/minute")
async def compute_resume_ats_score(
    request: Request,
    payload: AtsScoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.ats_service import compute_ats_score

    # Get resume text from specific doc or most recent primary resume
    resume_text = ""
    if payload.document_id:
        result = await db.execute(
            select(UserDocument).where(
                UserDocument.id == payload.document_id,
                UserDocument.user_id == current_user.id,
                UserDocument.doc_type == "resume",
            )
        )
        doc = result.scalar_one_or_none()
        if doc:
            resume_text = doc.raw_text or ""
    else:
        result = await db.execute(
            select(UserDocument).where(
                UserDocument.user_id == current_user.id,
                UserDocument.doc_type == "resume",
                UserDocument.is_primary == True,  # noqa: E712
            ).order_by(UserDocument.embedded_at.desc().nulls_last())
        )
        doc = result.scalar_one_or_none()
        if doc:
            resume_text = doc.raw_text or ""

    if not resume_text:
        raise HTTPException(status_code=404, detail="No resume found. Upload a resume first.")

    loop = asyncio.get_running_loop()
    score_result = await loop.run_in_executor(
        None, compute_ats_score, resume_text, payload.jd_text
    )
    return AtsScoreResponse(**score_result.__dict__)



# ---------------------------------------------------------------------------
# Resume Persona endpoints
# ---------------------------------------------------------------------------


class PersonaCreateRequest(BaseModel):
    name: str = Field(max_length=100)
    description: str = Field(default="", max_length=500)
    target_keywords: list[str] = Field(default_factory=list)
    primary_resume_id: uuid.UUID | None = None


class PersonaUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    target_keywords: list[str] | None = None
    primary_resume_id: uuid.UUID | None = None


@router.get("/personas")
async def list_personas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.db import ResumePersona

    result = await db.execute(
        select(ResumePersona).where(ResumePersona.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/personas", status_code=201)
async def create_persona(
    body: PersonaCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.db import ResumePersona

    # Enforce max 10
    count_result = await db.execute(
        select(ResumePersona).where(ResumePersona.user_id == current_user.id)
    )
    if len(count_result.scalars().all()) >= 10:
        raise HTTPException(status_code=400, detail="Maximum 10 personas allowed")

    persona = ResumePersona(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        target_keywords=body.target_keywords,
        primary_resume_id=body.primary_resume_id,
    )
    db.add(persona)
    await db.flush()
    return persona


@router.put("/personas/{persona_id}")
async def update_persona(
    persona_id: uuid.UUID,
    body: PersonaUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.db import ResumePersona

    result = await db.execute(
        select(ResumePersona).where(
            ResumePersona.id == persona_id,
            ResumePersona.user_id == current_user.id,
        )
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    if body.name is not None:
        persona.name = body.name
    if body.description is not None:
        persona.description = body.description
    if body.target_keywords is not None:
        persona.target_keywords = body.target_keywords
    if body.primary_resume_id is not None:
        persona.primary_resume_id = body.primary_resume_id
    return persona


@router.delete("/personas/{persona_id}", status_code=204)
async def delete_persona(
    persona_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.db import ResumePersona
    from sqlalchemy import delete

    result = await db.execute(
        delete(ResumePersona).where(
            ResumePersona.id == persona_id,
            ResumePersona.user_id == current_user.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Persona not found")
