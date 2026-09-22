import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.email_agent import email_agent_node
from app.agents.state import AgentState
from app.api.v1.deps import get_current_user, get_db
from app.api.v1.run_utils import CLIENT_SAFE_AGENT_ERROR
from app.core.rate_limit import limiter
from app.models.db import AgentRun, User
from app.services.gmail_service import GmailSendError

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
    recipient_email: str | None = None


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
        saved_subject = out.get("subject")
        subject = saved_subject if isinstance(saved_subject, str) else f"Follow-up on {role} at {company}"
        body = out.get("body") if isinstance(out.get("body"), str) else ""
        recipient_email = out.get("recipient") if isinstance(out.get("recipient"), str) else None
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
                recipient_email=recipient_email,
            )
        )
    return drafts


class ComposeRequest(BaseModel):
    company: str = Field(max_length=500)
    role: str = Field(max_length=500)
    recipient_email: EmailStr
    application_id: uuid.UUID | None = None
    subject: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=20000)


class GmailDraftRequest(BaseModel):
    recipient_email: EmailStr
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=20000)


@router.post("/gmail-drafts", response_model=dict)
@limiter.limit("10/minute")
async def save_gmail_draft(
    request: Request,
    payload: GmailDraftRequest,
    current_user: User = Depends(get_current_user),
):
    from app.services.gmail_service import GmailMCPClient

    try:
        draft = GmailMCPClient(str(current_user.id)).save_draft(
            str(payload.recipient_email), payload.subject, payload.body
        )
    except GmailSendError as exc:
        logger.warning("Gmail draft save failed for user %s: %s", current_user.id, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"id": draft.get("id"), "status": "saved"}


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


class InboxCleanupEmail(BaseModel):
    id: str
    from_: str = Field(alias="from")
    subject: str
    date: str
    unsubscribe_url: str | None = None


class InboxCleanupArchiveRequest(BaseModel):
    message_ids: list[str] = Field(min_length=1, max_length=50)


def _header_value(headers: list[dict], name: str) -> str:
    for header in headers:
        if isinstance(header, dict) and header.get("name", "").lower() == name.lower():
            value = header.get("value")
            return value if isinstance(value, str) else ""
    return ""


def _first_https_unsubscribe_url(list_unsubscribe: str) -> str | None:
    # Typical raw header: "<mailto:x@y.com>, <https://example.com/unsub>"
    for token in list_unsubscribe.split(","):
        candidate = token.strip().strip("<>").strip()
        if candidate.lower().startswith("https://"):
            return candidate
    return None


@router.get("/inbox-cleanup", response_model=list[InboxCleanupEmail])
@limiter.limit("10/minute")
async def list_inbox_cleanup(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    from app.services.gmail_service import GmailMCPClient

    client = GmailMCPClient(str(current_user.id))
    messages = client.search_threads(
        "category:promotions OR category:updates newer_than:30d", max_results=25
    )

    results: list[InboxCleanupEmail] = []
    for message in messages:
        message_id = message.get("id") if isinstance(message, dict) else None
        if not message_id:
            continue
        metadata = client.get_message_metadata(message_id)
        payload = metadata.get("payload") if isinstance(metadata, dict) else None
        headers = payload.get("headers", []) if isinstance(payload, dict) else []
        list_unsubscribe = _header_value(headers, "List-Unsubscribe")
        results.append(
            InboxCleanupEmail(
                id=message_id,
                **{"from": _header_value(headers, "From")},
                subject=_header_value(headers, "Subject"),
                date=_header_value(headers, "Date"),
                unsubscribe_url=_first_https_unsubscribe_url(list_unsubscribe)
                if list_unsubscribe
                else None,
            )
        )
    return results


@router.post("/inbox-cleanup/archive", response_model=dict)
@limiter.limit("10/minute")
async def archive_inbox_cleanup(
    request: Request,
    payload: InboxCleanupArchiveRequest,
    current_user: User = Depends(get_current_user),
):
    from app.services.gmail_service import GmailMCPClient

    client = GmailMCPClient(str(current_user.id))
    archived = sum(1 for message_id in payload.message_ids if client.archive_message(message_id))
    return {"archived": archived}


@router.post("/approve/{run_id}", response_model=dict)
async def approve_and_send(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Locked so a second concurrent approval of the same run sees the
    # status flip below before it can read a stale "awaiting_approval".
    result = await db.execute(
        select(AgentRun).where(
            AgentRun.id == uuid.UUID(run_id),
            AgentRun.user_id == current_user.id,
        ).with_for_update()
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

    # Claim the run before sending — a concurrent second approval's
    # row-locked read now sees "running", not "awaiting_approval", and
    # 400s above instead of reaching send_approved_email at all. That
    # function's own outbound_messages claim is the second, independent
    # guard against the same email going out twice.
    run.status = "running"
    await db.commit()

    from app.services.workflow_service import send_approved_email

    try:
        result = await send_approved_email(current_user.id, run.id, recipient, subject, body)
    except GmailSendError as exc:
        # Actionable Gmail reason (scopes, API disabled, revoked token) — safe to show.
        logger.warning("Email approval send failed for run %s: %s", run_id, exc)
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Email approval send failed for run %s: %s", run_id, exc)
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=502, detail="Email send failed") from exc

    run.status = "completed" if result.get("sent") else "failed"
    run.completed_at = datetime.now(timezone.utc)
    run.output = {**pending, **result}
    await db.commit()
    return {"status": "sent" if result.get("sent") else "unknown", "recipient": recipient}
