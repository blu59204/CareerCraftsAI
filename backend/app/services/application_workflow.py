"""Application preparation and a separate, approval-bound submit capability.

Preparation uses DOM field mapping, never a general-purpose browser agent with
unrestricted click tools. Unknown questions/navigation are handed to the user.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.db import AgentRun, BrowserSession, JobApplication, UserDocument
from app.services.sandbox_service import (
    acquire_session, browser_page, save_account_state, validate_browser_url,
)

SUBMIT_NAME = re.compile(r"^(submit(?: your)? application|send application|submit)$", re.I)
CONFIRMATION = re.compile(
    r"application (?:has been |was )?(?:successfully )?submitted|thank you for applying|we have received your application",
    re.I,
)

# No passwords, tokens or hidden fields are included in the review snapshot.
FORM_SNAPSHOT = """() => Array.from(document.querySelectorAll('input,select,textarea'))
 .filter(e => e.type !== 'password' && e.type !== 'hidden' && e.getClientRects().length)
 .map((e) => ({name:e.name, id:e.id, type:e.type,
 label:(e.labels?.[0]?.innerText || e.getAttribute('aria-label') || e.placeholder || e.name || '').trim(),
 value:e.type === 'file' ? Array.from(e.files || []).map(f=>f.name).join(',') : e.value,
 checked:e.checked || false, required:e.required || false}))"""


async def review_snapshot(page) -> dict:
    fields = await page.evaluate(FORM_SNAPSHOT)
    forms = await page.locator("form").evaluate_all("items => items.map(f => ({action:f.action, method:f.method}))")
    controls = await page.get_by_role("button", name=SUBMIT_NAME).all_text_contents()
    snapshot = {"url": page.url, "fields": fields, "forms": forms, "submit_controls": controls}
    snapshot["fingerprint"] = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return snapshot


def checkpoint(pending: dict, kind: str, message: str, **extra) -> dict:
    return {"status": "awaiting_approval", "pending_action": {
        **pending, **extra, "type": kind, "message": message,
    }}


async def load_resume(user_id: uuid.UUID, document_id: str) -> tuple[bytes, str]:
    from app.services.storage_service import download_file
    async with AsyncSessionLocal() as db:
        document = (await db.execute(select(UserDocument).where(
            UserDocument.id == uuid.UUID(document_id), UserDocument.user_id == user_id,
        ))).scalar_one_or_none()
        if not document or document.doc_type != "resume":
            raise ValueError("Approved resume is unavailable")
    content = await asyncio.to_thread(download_file, document.storage_path, str(user_id))
    if len(content) > 10 * 1024 * 1024 or not content.startswith(b"%PDF"):
        raise ValueError("Resume must be a PDF smaller than 10 MB")
    return content, hashlib.sha256(content).hexdigest()


async def fill_known_fields(page, user_id: str) -> None:
    from app.services.form_filler_service import build_user_form_profile
    profile = await asyncio.to_thread(build_user_form_profile, user_id)
    mapping = {
        "first name": profile.first_name, "last name": profile.last_name,
        "full name": profile.full_name, "name": profile.full_name,
        "email": profile.email, "email address": profile.email,
        "phone": profile.phone, "phone number": profile.phone,
        "linkedin": profile.linkedin_url, "linkedin url": profile.linkedin_url,
    }
    fields = page.locator("input,textarea")
    for index in range(await fields.count()):
        field = fields.nth(index)
        if not await field.is_visible() or not await field.is_editable():
            continue
        kind = (await field.get_attribute("type") or "text").lower()
        if kind not in {"text", "email", "tel", "url"} or await field.input_value():
            continue
        label = await field.evaluate("e => e.labels?.[0]?.innerText || e.getAttribute('aria-label') || e.placeholder || e.name || ''")
        label = re.sub(r"[_*:\s]+", " ", label).strip().lower()
        value = mapping.get(label)
        if value:
            await field.fill(value)


async def run_application_stage(run: AgentRun, pending: dict) -> dict:
    kind = pending["type"]
    validate_browser_url(pending["job_url"])
    session = await acquire_session(str(run.user_id), str(run.id))
    async with browser_page(session) as (context, page):
        if kind == "browser_prepare":
            await page.goto(pending["job_url"], wait_until="domcontentloaded", timeout=30000)
            await fill_known_fields(page, str(run.user_id))
        if kind in {"browser_prepare", "browser_input"}:
            await fill_known_fields(page, str(run.user_id))
            document_id = pending.get("pdf_document_id")
            if not document_id:
                raise ValueError("No approved resume document attached")
            content, digest = await load_resume(run.user_id, document_id)
            if pending.get("resume_sha256") and pending["resume_sha256"] != digest:
                raise ValueError("Approved resume content changed")
            upload = page.locator('input[type="file"]')
            if await upload.count() == 1:
                await upload.set_input_files({"name": "resume.pdf", "mimeType": "application/pdf", "buffer": content})
                pending = {**pending, "resume_sha256": digest, "resume_uploaded": True}
            snapshot = await review_snapshot(page)
            submit = page.get_by_role("button", name=SUBMIT_NAME)
            missing = any(f["required"] and not f["value"] and not f["checked"] for f in snapshot["fields"])
            ready = (
                await submit.count() == 1 and await submit.is_visible()
                and await submit.is_enabled() and not missing and pending.get("resume_uploaded", False)
                and not await page.locator('input[type="password"]:visible').count()
            )
            await save_account_state(session, context)
            next_type = "browser_review" if ready else "browser_input"
            async with AsyncSessionLocal() as db:
                saved = await db.get(BrowserSession, session.id)
                if saved is None:
                    raise RuntimeError("Browser session expired; prepare a new application for review")
                saved.status = "review" if ready else "input"
                saved.review = snapshot
                await db.commit()
            return checkpoint(
                pending, next_type,
                "Review the completed form and approve its final submission." if ready else
                "Open the browser to log in, handle verification, navigate to the form, or fill missing answers. Then continue preparation.",
                session_id=str(session.id), form=snapshot,
            )

        # This stage is created only by the locked, authenticated approval endpoint.
        expected = pending.get("form", {}).get("fingerprint")
        snapshot = await review_snapshot(page)
        if not expected or snapshot["fingerprint"] != expected:
            return checkpoint(pending, "browser_input", "The form changed. Prepare and review it again.", form=snapshot)
        _, digest = await load_resume(run.user_id, pending["pdf_document_id"])
        if digest != pending.get("resume_sha256"):
            raise ValueError("Resume changed after approval")
        submit = page.get_by_role("button", name=SUBMIT_NAME)
        if await submit.count() != 1 or not await submit.is_enabled():
            return checkpoint(pending, "browser_input", "The submit control changed. Review the form again.", form=snapshot)
        # Never retry this click: timeout/disconnection afterward is an unknown outcome.
        if await page.get_by_text(CONFIRMATION).count():
            return {"status": "failed", "result": {"outcome": "unknown", "message": "An existing confirmation was found; inspect the portal before applying again"}}
        try:
            await submit.click(timeout=15000, no_wait_after=True)
        except Exception:
            return {"status": "failed", "result": {
                "outcome": "unknown", "job_url": pending["job_url"],
                "message": "Submission may have been triggered but could not be confirmed. Check the portal before retrying.",
            }}
        try:
            await page.get_by_text(CONFIRMATION).first.wait_for(timeout=15000)
            receipt = (await page.locator("body").inner_text())[:12000]
            match = CONFIRMATION.search(receipt)
            if not match:
                raise ValueError("No confirmation found")
        except Exception:
            return {"status": "failed", "result": {
                "outcome": "unknown", "job_url": pending["job_url"],
                "message": "Submission was attempted but could not be confirmed. Check the portal before retrying.",
            }}
        await save_account_state(session, context)
        from datetime import datetime, timezone
        async with AsyncSessionLocal() as db:
            existing = (await db.execute(select(JobApplication).where(
                JobApplication.user_id == run.user_id, JobApplication.job_url == pending["job_url"],
            ).limit(1))).scalars().first()
            if not existing:
                existing = JobApplication(user_id=run.user_id, job_url=pending["job_url"],
                                          company=pending.get("company", "Unknown"), role=pending.get("role", "Unknown"))
                db.add(existing)
            existing.status = "applied"
            existing.applied_at = datetime.now(timezone.utc)
            existing.resume_id = uuid.UUID(pending["pdf_document_id"])
            await db.commit()
        return {"status": "completed", "result": {
            "outcome": "submitted", "job_url": pending["job_url"],
            "confirmation": match.group(0), "confirmation_url": page.url,
        }}
