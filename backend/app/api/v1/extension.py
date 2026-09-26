"""CareerCraft browser extension API.

Two audiences:
* /extension/*        — the signed-in web app (Clerk JWT): pair a browser,
                        list/revoke devices, see and cancel browser tasks.
* /extension/device/* — the extension itself (device token "ccx_…"):
                        claim work, fetch a fill plan, report progress.
                        Exempt from the Clerk middleware in main.py.

Progress reports are relayed to the application's AutoApplyWorkflow as
signals; the workflow alone records the final outcome.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.service import RPCError

from app.api.v1.deps import get_current_user, get_db
from app.core.event_bus import publish
from app.core.rate_limit import limiter
from app.models.db import AgentRun, ExtensionDevice, ExtensionTask, User
from app.services import extension_service
from app.workflows.starters import WorkflowUnavailable

router = APIRouter(prefix="/extension", tags=["extension"])
logger = logging.getLogger(__name__)

PROGRESS_STAGES = {"claimed", "filling", "needs_input", "review", "login_required"}
TERMINAL_STAGES = {"submitted", "failed", "cancelled"}
STAGE_MESSAGES = {
    "claimed": "Your browser picked up this application",
    "filling": "Filling the application in your browser",
    "needs_input": "A few questions need your answer in the extension panel",
    "review": "Ready for your review — press Submit in the extension panel",
    "login_required": "Sign in to the job site in your browser; the extension will continue",
}


# ── Web app (Clerk) ────────────────────────────────────────────────────


class PairRequest(BaseModel):
    name: str = Field(default="Browser", max_length=100)


@router.post("/pair")
@limiter.limit("10/hour")
async def pair(
    request: Request,
    body: PairRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a device token. It is returned once — paste it into the
    extension (or let the web app hand it over) and it is never shown again."""
    device, token = await extension_service.pair_device(db, current_user.id, body.name)
    return {"device_id": str(device.id), "name": device.name, "token": token}


@router.get("/devices")
async def list_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        (
            await db.execute(
                select(ExtensionDevice)
                .where(
                    ExtensionDevice.user_id == current_user.id,
                    ExtensionDevice.revoked_at.is_(None),
                )
                .order_by(ExtensionDevice.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "devices": [
            {
                "id": str(d.id),
                "name": d.name,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
            }
            for d in rows
        ]
    }


@router.delete("/devices/{device_id}")
async def revoke_device(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = (
        await db.execute(
            select(ExtensionDevice).where(
                ExtensionDevice.id == device_id,
                ExtensionDevice.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    device.revoked_at = datetime.now(UTC)
    await db.commit()
    return {"status": "revoked"}


@router.get("/tasks")
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        (
            await db.execute(
                select(ExtensionTask)
                .where(ExtensionTask.user_id == current_user.id)
                .order_by(ExtensionTask.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return {"tasks": [extension_service.task_view(t) for t in rows]}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = (
        await db.execute(
            select(ExtensionTask).where(
                ExtensionTask.id == task_id,
                ExtensionTask.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in extension_service_open_statuses():
        return {"status": task.status}
    await _signal(
        task.workflow_id,
        {"stage": "cancelled", "details": {"message": "Cancelled from the web app"}},
    )
    return {"status": "cancelling"}


def extension_service_open_statuses() -> tuple[str, ...]:
    from app.workflows.extension_activities import OPEN_TASK_STATUSES

    return OPEN_TASK_STATUSES


# ── Extension (device token) ───────────────────────────────────────────


async def get_device(request: Request, db: AsyncSession = Depends(get_db)) -> ExtensionDevice:
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
    device = await extension_service.authenticate(db, token) if token else None
    if device is None:
        raise HTTPException(status_code=401, detail="Extension is not connected — pair it again")
    return device


async def _device_task(
    db: AsyncSession, device: ExtensionDevice, task_id: uuid.UUID
) -> ExtensionTask:
    task = await extension_service.get_device_task(db, device, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.device_id not in (None, device.id):
        raise HTTPException(
            status_code=409, detail="Another browser is working on this application"
        )
    return task


async def _signal(workflow_id: str, update: dict) -> None:
    from app.workflows.starters import signal_extension_update

    try:
        await signal_extension_update(workflow_id, update)
    except WorkflowUnavailable as exc:
        raise HTTPException(status_code=503, detail="Application service unavailable") from exc
    except RPCError as exc:
        # The workflow already finished (e.g. it expired): nothing to update.
        logger.info("Extension update for closed workflow %s: %s", workflow_id, exc)
        raise HTTPException(status_code=409, detail="This application is no longer active") from exc


@router.get("/device/me")
async def device_me(
    device: ExtensionDevice = Depends(get_device),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, device.user_id)
    return {
        "device_id": str(device.id),
        "device_name": device.name,
        "user": {"email": user.email if user else None, "name": user.full_name if user else None},
    }


@router.delete("/device/me")
async def device_revoke_self(
    device: ExtensionDevice = Depends(get_device), db: AsyncSession = Depends(get_db)
):
    """The extension disconnects or re-pairs: retire its own token."""
    device.revoked_at = datetime.now(UTC)
    await db.commit()
    return {"status": "revoked"}


@router.post("/device/tasks/claim")
@limiter.limit("120/minute")
async def claim_task(
    request: Request,
    device: ExtensionDevice = Depends(get_device),
    db: AsyncSession = Depends(get_db),
):
    task = await extension_service.claim_next_task(db, device)
    if task is None:
        return Response(status_code=204)
    await _signal(task.workflow_id, {"stage": "claimed"})
    await _record_progress(db, task, "claimed", STAGE_MESSAGES["claimed"])
    return extension_service.task_view(task)


@router.get("/device/tasks/{task_id}")
async def get_task(
    task_id: uuid.UUID,
    device: ExtensionDevice = Depends(get_device),
    db: AsyncSession = Depends(get_db),
):
    return extension_service.task_view(await _device_task(db, device, task_id))


class TaskEvent(BaseModel):
    stage: Literal[
        "filling",
        "needs_input",
        "review",
        "login_required",
        "submitted",
        "failed",
        "cancelled",
    ]
    message: str | None = Field(default=None, max_length=500)
    confirmation_text: str | None = Field(default=None, max_length=2000)
    confirmation_url: str | None = Field(default=None, max_length=2000)
    error: str | None = Field(default=None, max_length=1000)


async def _record_progress(db: AsyncSession, task: ExtensionTask, stage: str, message: str) -> None:
    task.status = stage
    output = {
        "type": "extension_apply",
        "stage": stage,
        "message": message,
        "task_id": str(task.id),
        "job_url": (task.payload or {}).get("job_url"),
        "platform": (task.payload or {}).get("platform"),
    }
    if task.run_id:
        run = await db.get(AgentRun, task.run_id, with_for_update=True)
        if run is not None and run.status in {"queued", "running"}:
            run.status = "running"
            run.output = output
    await db.commit()
    if task.run_id:
        publish(str(task.run_id), "thinking", output)


@router.post("/device/tasks/{task_id}/events")
@limiter.limit("240/minute")
async def task_event(
    request: Request,
    task_id: uuid.UUID,
    event: TaskEvent,
    device: ExtensionDevice = Depends(get_device),
    db: AsyncSession = Depends(get_db),
):
    task = await _device_task(db, device, task_id)
    if task.status not in extension_service_open_statuses():
        return {"status": task.status, "active": False}

    if event.stage in TERMINAL_STAGES:
        details = {
            k: v
            for k, v in {
                "message": event.message,
                "confirmation_text": event.confirmation_text,
                "confirmation_url": event.confirmation_url,
                "error": event.error,
            }.items()
            if v
        }
        await _signal(task.workflow_id, {"stage": event.stage, "details": details})
        return {"status": event.stage, "active": False}

    await _signal(task.workflow_id, {"stage": event.stage})
    await _record_progress(db, task, event.stage, event.message or STAGE_MESSAGES[event.stage])
    return {"status": event.stage, "active": True}


class PlanRequest(BaseModel):
    url: str | None = Field(default=None, max_length=2000)
    fields: list[dict[str, Any]] = Field(default_factory=list, max_length=200)


@router.post("/device/tasks/{task_id}/plan")
@limiter.limit("60/minute")
async def plan(
    request: Request,
    task_id: uuid.UUID,
    body: PlanRequest,
    device: ExtensionDevice = Depends(get_device),
    db: AsyncSession = Depends(get_db),
):
    task = await _device_task(db, device, task_id)
    if task.status not in extension_service_open_statuses():
        raise HTTPException(status_code=409, detail="This application is no longer active")
    return await extension_service.plan_fields(db, task, body.fields)


@router.get("/device/tasks/{task_id}/resume")
async def task_resume(
    task_id: uuid.UUID,
    device: ExtensionDevice = Depends(get_device),
    db: AsyncSession = Depends(get_db),
):
    from app.models.db import UserDocument
    from app.services.storage_service import download_file

    task = await _device_task(db, device, task_id)
    document_id = (task.payload or {}).get("resume_document_id")
    if not document_id:
        raise HTTPException(status_code=404, detail="No resume attached to this application")
    document = (
        await db.execute(
            select(UserDocument).where(
                UserDocument.id == uuid.UUID(document_id),
                UserDocument.user_id == task.user_id,
            )
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    content = await asyncio.to_thread(download_file, document.storage_path, str(task.user_id))
    filename = (document.filename or "resume.pdf").replace('"', "")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


class AnswerRequest(BaseModel):
    label: str = Field(min_length=1, max_length=500)
    value: str | bool | list[str]
    question_key: str | None = Field(default=None, max_length=200)


@router.post("/device/answers")
@limiter.limit("120/minute")
async def save_answer(
    request: Request,
    body: AnswerRequest,
    device: ExtensionDevice = Depends(get_device),
    db: AsyncSession = Depends(get_db),
):
    """Remember an answer the user typed in the review panel, so the same
    question is filled automatically next time."""
    from app.applications import profile_service

    key = body.question_key or extension_service.answer_key(body.label)
    await profile_service.save_approved_answer(db, device.user_id, key, body.label, body.value)
    await db.commit()
    return {"question_key": key}


class DecideRequest(BaseModel):
    state: Any
    questions: dict[str, dict[str, Any]]


@router.post("/device/decide")
@limiter.limit("300/minute")
async def decide(
    request: Request,
    body: DecideRequest,
    device: ExtensionDevice = Depends(get_device),
):
    """Typed in-page decisions (which button advances the form, is this a
    confirmation page, …) via the configured System One model."""
    from app.services import decision_engine

    state = body.state
    if len(str(state)) > decision_engine.MAX_STATE_CHARS:
        raise HTTPException(status_code=413, detail="State too large")
    try:
        return await decision_engine.decide(state, body.questions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
