import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.email_agent import email_agent_node
from app.agents.state import AgentState
from app.api.v1.deps import get_current_user, get_db
from app.api.v1.run_utils import CLIENT_SAFE_AGENT_ERROR
from app.core.rate_limit import limiter
from app.models.db import AgentRun, User
from app.services.gmail_service import GmailMCPClient, GmailSendError

router = APIRouter(prefix="/email", tags=["email"])
logger = logging.getLogger(__name__)


def _relative_time(dt: datetime) -> str:
    """Return a human-readable relative time string from a datetime."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 3600:
        hours = max(1, seconds // 60)
        return f"{hours}m ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h ago"
    days = seconds // 86400
    if days == 1:
        return "Yesterday"
    return f"{days}d ago"


class EmailDraft(BaseModel):
    id: str
    subject: str
    company: str
    timestamp: str
    initial: str
    body: str
    status: str


@router.get("/drafts", response_model=list[EmailDraft])
@limiter.limit("30/minute")
async def list_drafts(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentRun)
        .where(
            AgentRun.agent_type == "email",
            AgentRun.user_id == current_user.id,
        )
        .order_by(desc(AgentRun.started_at))
        .limit(20)
    )
    runs = result.scalars().all()

    drafts: list[EmailDraft] = []
    for run in runs:
        inp: dict = run.input or {}
        out: dict = run.output or {}
        company = inp.get("company", "")
        role = inp.get("role", "role")
        subject = f"Follow-up on {role} at {company}"
        body = out.get("draft", {}).get("body", "") if isinstance(out.get("draft"), dict) else ""
        initial = company[0].upper() if company else "?"
        timestamp = _relative_time(run.started_at) if run.started_at else "?"
        drafts.append(
            EmailDraft(
                id=str(run.id),
                subject=subject,
                company=company,
                timestamp=timestamp,
                initial=initial,
                body=body,
                status=run.status or "unknown",
            )
        )
    return drafts


class ComposeRequest(BaseModel):
    company: str = Field(max_length=500)
    role: str = Field(max_length=500)
    recipient_email: str
    application_id: uuid.UUID | None = None
    subject: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=20000)


@router.post("/compose", response_model=dict)
@limiter.limit("10/minute")
async def compose_email(
    request: Request,
    payload: ComposeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="email",
        status="running",
        input={"company": payload.company, "role": payload.role},
    )
    db.add(agent_run)
    await db.flush()

    state = AgentState(
        user_id=str(current_user.id),
        run_id=run_id,
        task_type="email",
        messages=[HumanMessage(content=f"Draft email for {payload.role} at {payload.company}")],
        context={
            "company": payload.company,
            "role": payload.role,
            "recipient_email": payload.recipient_email,
        },
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )

    result_state = await asyncio.get_running_loop().run_in_executor(None, email_agent_node, state)

    agent_run.status = result_state["status"]
    agent_run.completed_at = datetime.now(timezone.utc)
    if result_state.get("pending_action"):
        pending_action = dict(result_state["pending_action"])
        if payload.subject:
            pending_action["subject"] = payload.subject
        if payload.body:
            pending_action["body"] = payload.body
        agent_run.output = pending_action

    if result_state["status"] == "failed":
        logger.warning("Email compose agent failed for run %s: %s", run_id, result_state.get("error"))
        raise HTTPException(status_code=500, detail=CLIENT_SAFE_AGENT_ERROR)

    return {
        "run_id": run_id,
        "status": result_state["status"],
        "draft": result_state.get("pending_action"),
    }


@router.post("/approve/{run_id}", response_model=dict)
async def approve_and_send(
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
    if run.status != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Run is {run.status}, not awaiting_approval")

    pending = run.output or {}
    if pending.get("type") != "send_email":
        raise HTTPException(status_code=400, detail="No email pending for this run")

    recipient = pending.get("recipient")
    subject = pending.get("subject")
    body = pending.get("body")
    if not recipient or not subject or not body:
        raise HTTPException(
            status_code=422,
            detail="Pending email is missing recipient, subject, or body",
        )

    try:
        gmail = GmailMCPClient(str(current_user.id))
        gmail.send_message(to=recipient, subject=subject, body=body)
    except GmailSendError as exc:
        # Actionable Gmail reason (scopes, API disabled, revoked token) — safe to show.
        logger.warning("Email approval send failed for run %s: %s", run_id, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Email approval send failed for run %s: %s", run_id, exc)
        raise HTTPException(status_code=502, detail="Email send failed") from exc

    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    return {"status": "sent", "recipient": recipient}
