import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness import get_harness
from app.api.v1.deps import get_current_user, get_db
from app.api.v1.run_utils import CLIENT_SAFE_AGENT_ERROR
from app.core.database import AsyncSessionLocal
from app.core.event_bus import emit, get_queue, stream_events
from app.core.rate_limit import limiter
from app.models.db import AgentRun, User

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)
AGENT_RUN_TIMEOUT_SECONDS = 120

VALID_TASKS = {
    "resume_optimize", "job_search", "linkedin_optimize", "email", "interview_prep",
    "cover_letter", "interview_coach", "evaluate_answer", "salary_intelligence",
    "company_research", "nl_job_search", "linkedin_outreach", "email_monitor",
}


class RunRequest(BaseModel):
    task_type: str
    context: dict = {}


class RunResponse(BaseModel):
    run_id: str
    status: str


class AutoApplyRequest(BaseModel):
    search_query: str
    location: str = "Remote"
    max_applications: int = 5
    platforms: list[str] | None = None
    linkedin_email: str | None = None
    linkedin_password: str | None = None
    live_browser: bool = False


class ApproveRequest(BaseModel):
    approved: bool


class AgentRunResponse(BaseModel):
    id: uuid.UUID
    agent_type: str
    status: str
    input: dict | None
    output: dict | None
    duration_ms: int | None
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("/runs", response_model=list[AgentRunResponse])
@limiter.limit("30/minute")
async def list_runs(
    request: Request,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recent agent runs for the current user."""
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.user_id == current_user.id)
        .order_by(AgentRun.started_at.desc())
        .limit(min(limit, 50))
    )
    return result.scalars().all()


@router.post("/run", response_model=RunResponse)
@limiter.limit("10/minute")
async def start_agent_run(
    request: Request,
    payload: RunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.task_type not in VALID_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"task_type must be one of: {VALID_TASKS}",
        )

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type=payload.task_type,
        status="running",
        input={
            "task_type": payload.task_type,
            "context_keys": list(payload.context.keys()),
        },
    )
    db.add(agent_run)
    await db.flush()
    get_queue(run_id)

    async def _run() -> None:
        started = datetime.now(timezone.utc)

        async def _finish_run(status: str, output: dict | None, duration_ms: int | None = None) -> None:
            async with AsyncSessionLocal() as fresh_db:
                res = await fresh_db.execute(
                    select(AgentRun).where(AgentRun.id == uuid.UUID(run_id))
                )
                run = res.scalar_one_or_none()
                if run:
                    run.status = status
                    run.output = output
                    run.duration_ms = duration_ms
                    run.completed_at = datetime.now(timezone.utc)
                await fresh_db.commit()

        try:
            harness = await get_harness()
            harness_result = await asyncio.wait_for(
                harness.run(
                    user_id=str(current_user.id),
                    task_type=payload.task_type,
                    context=payload.context,
                    user_settings={},   # user model settings resolved inside agents
                    run_id=run_id,
                ),
                timeout=AGENT_RUN_TIMEOUT_SECONDS,
            )
            final_status = harness_result.get("status", "failed")
            final_output = harness_result.get("result") or harness_result.get("pending_action")

            # Forward SSE events based on harness outcome
            if final_status == "awaiting_approval":
                emit(run_id, "checkpoint", final_output or {})
            elif final_status == "failed":
                if harness_result.get("error"):
                    logger.warning("Agent run %s failed: %s", run_id, harness_result.get("error"))
                emit(run_id, "error", CLIENT_SAFE_AGENT_ERROR)
                final_output = {"error": CLIENT_SAFE_AGENT_ERROR}
            elif final_status == "completed":
                emit(run_id, "complete", final_output or {})

            await _finish_run(final_status, final_output, harness_result.get("duration_ms"))
        except asyncio.TimeoutError:
            error = f"Agent run timed out after {AGENT_RUN_TIMEOUT_SECONDS} seconds"
            logger.error("Agent run %s timed out", run_id)
            emit(run_id, "error", error)
            duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            await _finish_run("failed", {"error": error}, duration_ms)
        except Exception as exc:
            logger.error("Agent run %s background task failed: %s", run_id, exc, exc_info=True)
            # SSE events are client-visible; never emit raw exception text.
            emit(run_id, "error", CLIENT_SAFE_AGENT_ERROR)
            duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            await _finish_run("failed", {"error": CLIENT_SAFE_AGENT_ERROR}, duration_ms)

    asyncio.create_task(_run())
    return RunResponse(run_id=run_id, status="running")


async def _terminal_event_for_run(run_id: str) -> str | None:
    async with AsyncSessionLocal() as fresh_db:
        res = await fresh_db.execute(
            select(AgentRun).where(AgentRun.id == uuid.UUID(run_id))
        )
        run = res.scalar_one_or_none()
        if not run or run.status not in {"completed", "failed", "awaiting_approval"}:
            return None
        event_type = {
            "completed": "complete",
            "failed": "error",
            "awaiting_approval": "checkpoint",
        }[run.status]
        data = run.output or {}
        if run.status == "failed" and isinstance(data, dict):
            data = data.get("error") or "Unknown error"
        payload = json.dumps({"type": event_type, "data": data, "ts": int(datetime.now(timezone.utc).timestamp())})
        return f"data: {payload}\n\n"


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(AgentRun).where(
            AgentRun.id == uuid.UUID(run_id),
            AgentRun.user_id == current_user.id,
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Run not found")
    async def _stream_with_db_fallback():
        terminal = await _terminal_event_for_run(run_id)
        if terminal:
            yield terminal
            return

        try:
            async for event in stream_events(run_id):
                yield event
                if '"type":"ping"' in event or '"type": "ping"' in event:
                    terminal = await _terminal_event_for_run(run_id)
                    if terminal:
                        yield terminal
                        return
        except Exception as exc:
            logger.warning("SSE stream fallback polling for run %s: %s", run_id, exc)
            while True:
                terminal = await _terminal_event_for_run(run_id)
                if terminal:
                    yield terminal
                    return
                await asyncio.sleep(2)

    return StreamingResponse(
        _stream_with_db_fallback(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/{run_id}/approve", response_model=dict)
async def approve_or_cancel(
    run_id: str,
    payload: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(AgentRun).where(
            AgentRun.id == uuid.UUID(run_id),
            AgentRun.user_id == current_user.id,
        )
    )
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "awaiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Run is {run.status}, not awaiting_approval",
        )

    if not payload.approved:
        run.status = "failed"
        run.output = {"error": "Action cancelled by user"}
        run.completed_at = datetime.now(timezone.utc)
        emit(run_id, "error", "Action cancelled by user")
        return {"status": "cancelled"}

    pending = run.output or {}
    action_type = pending.get("type", "")
    if action_type == "send_email":
        from app.services.gmail_service import GmailMCPClient

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
            gmail.send_message(recipient, subject, body)
        except Exception as exc:
            logger.warning("Approved email send failed for run %s: %s", run_id, exc)
            raise HTTPException(status_code=502, detail="Email send failed") from exc
    elif action_type == "submit_application":
        from app.models.db import JobApplication

        application_id = pending.get("application_id")
        if application_id:
            res = await db.execute(
                select(JobApplication).where(
                    JobApplication.id == uuid.UUID(application_id),
                    JobApplication.user_id == current_user.id,
                )
            )
            application = res.scalar_one_or_none()
            if application:
                application.status = "applied"
                application.applied_at = datetime.now(timezone.utc)
    elif action_type == "linkedin_edits":
        from app.core.model_router import _build_llm
        from app.core.sync_db import fetch_model_settings
        from app.services.browser_control_service import linkedin_update_profile

        model_settings = fetch_model_settings(str(current_user.id))
        if not model_settings:
            raise HTTPException(status_code=400, detail="No active model settings configured")
        llm = _build_llm(model_settings)
        try:
            browser_result = await linkedin_update_profile(
                llm=llm,
                user_id=str(current_user.id),
                headline=pending.get("headline"),
                about=pending.get("about"),
                live_browser=bool(pending.get("live_browser", True)),
                run_id=run_id,
            )
            pending = {**pending, "browser_result": browser_result[:1000]}
        except Exception as exc:
            logger.warning("Approved LinkedIn update failed for run %s: %s", run_id, exc)
            raise HTTPException(status_code=502, detail="LinkedIn update failed") from exc
    elif action_type == "salary_report_review":
        # Approval records that the user accepted the generated negotiation
        # script. The script itself is already persisted on salary_reports.
        pass
    elif action_type == "auto_apply_approval":
        from app.core.model_router import _build_llm
        from app.core.sync_db import fetch_model_settings
        from app.services.browser_control_service import linkedin_send_connection
        from app.services.gmail_service import GmailMCPClient

        actions = pending.get("actions_pending") or []
        if not isinstance(actions, list) or not actions:
            raise HTTPException(status_code=422, detail="No auto-apply actions pending")

        gmail: GmailMCPClient | None = None
        llm = None
        executed: list[dict] = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            item_type = action.get("action")
            if item_type == "send_email":
                recipient = action.get("to") or action.get("recipient")
                subject = action.get("subject")
                body = action.get("body")
                if not recipient or not subject or not body:
                    raise HTTPException(
                        status_code=422,
                        detail="Pending auto-apply email is missing recipient, subject, or body",
                    )
                try:
                    gmail = gmail or GmailMCPClient(str(current_user.id))
                    gmail.send_message(recipient, subject, body)
                    executed.append({"action": item_type, "to": recipient})
                except Exception as exc:
                    logger.warning("Auto-apply email send failed for run %s: %s", run_id, exc)
                    raise HTTPException(status_code=502, detail="Email send failed") from exc
            elif item_type == "send_linkedin_connection":
                profile_url = action.get("profile_url")
                note = action.get("note") or ""
                if not profile_url:
                    raise HTTPException(status_code=422, detail="Pending LinkedIn action is missing profile_url")
                try:
                    if llm is None:
                        model_settings = fetch_model_settings(str(current_user.id))
                        if not model_settings:
                            raise RuntimeError("No active model settings configured")
                        llm = _build_llm(model_settings)
                    await linkedin_send_connection(
                        llm=llm,
                        user_id=str(current_user.id),
                        profile_url=profile_url,
                        note=note,
                        live_browser=bool(pending.get("live_browser", True)),
                        run_id=run_id,
                    )
                    executed.append({"action": item_type, "profile_url": profile_url})
                except Exception as exc:
                    logger.warning("Auto-apply LinkedIn send failed for run %s: %s", run_id, exc)
                    raise HTTPException(status_code=502, detail="LinkedIn send failed") from exc
            else:
                raise HTTPException(status_code=422, detail=f"Unsupported auto-apply action: {item_type}")
        pending = {"type": action_type, "executed": executed}

    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    run.output = pending
    emit(run_id, "complete", {"approved": True, "action": action_type})
    await db.flush()
    return {"status": "completed", "action": action_type}



@router.post("/auto-apply")
@limiter.limit("3/hour")
async def auto_apply(
    request: Request,
    payload: AutoApplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger the fully automated job application pipeline.

    Chains: multi-platform search → score → find recruiter → tailor resume →
    prepare cold email + LinkedIn drafts, then waits for user approval.
    """
    from app.agents.auto_apply_pipeline import run_auto_apply_pipeline

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="auto_apply",
        status="running",
        input={
            "search_query": payload.search_query,
            "location": payload.location,
            "max_applications": payload.max_applications,
            "live_browser": payload.live_browser,
        },
    )
    db.add(agent_run)
    await db.commit()

    linkedin_creds = None
    if payload.linkedin_email and payload.linkedin_password:
        linkedin_creds = {"email": payload.linkedin_email, "password": payload.linkedin_password}

    # Run pipeline in background
    import asyncio

    async def _run_pipeline():
        try:
            result = await run_auto_apply_pipeline(
                user_id=str(current_user.id),
                search_query=payload.search_query,
                location=payload.location,
                max_applications=payload.max_applications,
                platforms=payload.platforms,
                linkedin_credentials=linkedin_creds,
                live_browser=payload.live_browser,
                run_id=run_id,
            )
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select as sel
                res = await session.execute(sel(AgentRun).where(AgentRun.id == uuid.UUID(run_id)))
                run = res.scalar_one_or_none()
                if run:
                    run.status = "awaiting_approval" if result.get("requires_approval") else "completed"
                    run.output = result
                    if run.status == "completed":
                        run.completed_at = datetime.now(timezone.utc)
                    await session.commit()
        except Exception as exc:
            logger.error("Auto-apply pipeline failed: %s", exc, exc_info=True)
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select as sel
                res = await session.execute(sel(AgentRun).where(AgentRun.id == uuid.UUID(run_id)))
                run = res.scalar_one_or_none()
                if run:
                    run.status = "failed"
                    run.output = {"error": CLIENT_SAFE_AGENT_ERROR}
                    run.completed_at = datetime.now(timezone.utc)
                    await session.commit()

    asyncio.create_task(_run_pipeline())

    return {"run_id": run_id, "status": "running", "message": "Auto-apply pipeline started"}
