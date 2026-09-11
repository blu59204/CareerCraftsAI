"""Authenticated browser takeover. No public CDP URLs or credential logging."""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.models.db import AgentRun, BrowserSession, User
from app.services.sandbox_service import browser_page, validate_browser_url

router = APIRouter(prefix="/browser", tags=["browser"])


class BrowserInput(BaseModel):
    action: Literal["click", "text", "key", "scroll", "navigate"]
    x: int = Field(default=0, ge=0, le=1280)
    y: int = Field(default=0, ge=0, le=900)
    text: str = Field(default="", max_length=10000)
    key: Literal["Tab", "Shift+Tab", "Backspace", "ArrowDown", "ArrowUp", "Escape", "ControlOrMeta+A"] = "Tab"
    delta: int = Field(default=500, ge=-1500, le=1500)


async def owned_session(db: AsyncSession, user: User, run_id: uuid.UUID, *, control=False):
    run = (await db.execute(select(AgentRun).where(
        AgentRun.id == run_id, AgentRun.user_id == user.id,
    ).with_for_update())).scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")
    session = (await db.execute(select(BrowserSession).where(
        BrowserSession.run_id == run_id, BrowserSession.user_id == user.id,
    ).with_for_update())).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "No browser session for this run")
    if session.expires_at <= datetime.now(timezone.utc) or session.status in {"closed", "closing", "failed"}:
        raise HTTPException(410, "Browser session expired; start a new application")
    if not session.sandbox_id or session.status == "provisioning":
        raise HTTPException(409, "Browser is still preparing; wait for its checkpoint")
    if run.status != "awaiting_approval":
        raise HTTPException(409, "Browser is controlled by the workflow; wait for its checkpoint")
    if control and (run.output or {}).get("type") != "browser_input":
        raise HTTPException(409, "This form is awaiting final review and is read-only")
    return run, session


@router.get("/{run_id}/frame")
async def frame(run_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    run, session = await owned_session(db, user, run_id)
    async with browser_page(session) as (_, page):
        shot = await page.screenshot(type="jpeg", quality=65)
        return {"image": base64.b64encode(shot).decode(), "url": page.url,
                "width": 1280, "height": 900, "expires_at": session.expires_at.isoformat(),
                "interactive": (run.output or {}).get("type") == "browser_input"}


@router.post("/{run_id}/input")
async def browser_input(run_id: uuid.UUID, payload: BrowserInput,
                        db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    _, session = await owned_session(db, user, run_id, control=True)
    async with browser_page(session) as (_, page):
        if payload.action == "click":
            # Do not let a form-filling handoff accidentally bypass final-form review.
            permitted = await page.evaluate(r"""({x,y}) => {
                const e = document.elementFromPoint(x,y)?.closest('button,input[type=submit],[role=button],a');
                if (!e) return true;
                const label = (e.innerText || e.value || e.getAttribute('aria-label') || '').trim();
                if (/submit|send application|finish|complete application/i.test(label)) return false;
                if ((e.type === 'submit' || (e.tagName === 'BUTTON' && e.form && !e.type)) &&
                    !/log\s?in|sign\s?in|continue|next|verify/i.test(label)) return false;
                return true;
            }""", {"x": payload.x, "y": payload.y})
            if not permitted:
                raise HTTPException(409, "Continue preparation, then approve the completed form to submit")
            await page.mouse.click(payload.x, payload.y)
        elif payload.action == "text":
            await page.keyboard.insert_text(payload.text)
        elif payload.action == "key":
            await page.keyboard.press(payload.key)
        elif payload.action == "scroll":
            await page.mouse.wheel(0, payload.delta)
        else:
            try:
                url = validate_browser_url(payload.text)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
    return {"ok": True}
