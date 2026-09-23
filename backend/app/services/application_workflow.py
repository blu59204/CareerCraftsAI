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

from app.applications.answer_resolver import resolve_fields
from app.applications.question_normalizer import normalize_question
from app.applications.validator import is_empty
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


async def claim_attempt_for_submit(attempt_id: str, approved_snapshot_hash: str | None):
    """Atomic awaiting_approval -> submitting transition.

    Returns the claimed ApplicationAttempt, or None if the attempt is not
    (or no longer) in awaiting_approval — meaning a concurrent caller already
    claimed it, or it is in some other state. Callers MUST NOT click Submit
    unless this returns a row: this is the single compare-and-swap guard
    that makes the external submit click at-most-once regardless of how
    many callers reach this point concurrently.
    """
    from app.models.db import ApplicationAttempt

    async with AsyncSessionLocal() as db:
        attempt = await db.get(ApplicationAttempt, uuid.UUID(attempt_id), with_for_update=True)
        if attempt is None or attempt.state != "awaiting_approval":
            return None
        attempt.state = "submitting"
        attempt.submission_token = str(uuid.uuid4())
        attempt.approved_snapshot_hash = approved_snapshot_hash
        await db.commit()
        return attempt


async def mark_attempt_awaiting_approval(attempt_id: str) -> None:
    from app.models.db import ApplicationAttempt

    async with AsyncSessionLocal() as db:
        attempt = await db.get(ApplicationAttempt, uuid.UUID(attempt_id), with_for_update=True)
        if attempt is None or attempt.state in {"submitting", "submitted", "verified"}:
            return
        attempt.state = "awaiting_approval"
        await db.commit()


async def mark_attempt_outcome_unknown(attempt_id: str, error: str) -> None:
    """A crash/timeout after the submit click: never automatically retried."""
    from app.models.db import ApplicationAttempt

    async with AsyncSessionLocal() as db:
        attempt = await db.get(ApplicationAttempt, uuid.UUID(attempt_id), with_for_update=True)
        if attempt is None or attempt.state != "submitting":
            return
        attempt.state = "outcome_unknown"
        attempt.last_error = error[:2000]
        await db.commit()


async def mark_attempt_verified(
    attempt_id: str, confirmation_text: str, confirmation_url: str,
) -> None:
    from datetime import datetime, timezone

    from app.models.db import ApplicationAttempt

    async with AsyncSessionLocal() as db:
        attempt = await db.get(ApplicationAttempt, uuid.UUID(attempt_id), with_for_update=True)
        if attempt is None:
            return
        now = datetime.now(timezone.utc)
        attempt.state = "verified"
        attempt.confirmation_text = confirmation_text[:12000]
        attempt.confirmation_url = confirmation_url
        attempt.submitted_at = now
        attempt.verified_at = now
        await db.commit()


async def run_application_stage(run: AgentRun, pending: dict) -> dict:
    # Local import: app.applications.adapters.generic imports SUBMIT_NAME/
    # CONFIRMATION back from this module, so a module-level import here would
    # be circular (this module wouldn't have finished defining them yet).
    from app.applications.adapters import detect_adapter

    kind = pending["type"]
    validate_browser_url(pending["job_url"])
    session = await acquire_session(str(run.user_id), str(run.id))
    async with browser_page(session) as (context, page):
        if kind == "browser_prepare":
            await page.goto(pending["job_url"], wait_until="domcontentloaded", timeout=30000)
            await fill_known_fields(page, str(run.user_id))
        # Detected once the page has (or already had) a chance to load, so
        # DOM-based fallback detection (e.g. an embedded Greenhouse widget on
        # a company's own domain) has real markup to inspect. GenericAdapter
        # always matches last, so `adapter` is never None.
        adapter = await detect_adapter(pending["job_url"], page)
        if kind in {"browser_prepare", "browser_input"}:
            # fill_known_fields does plain label->profile-field text fills
            # (name/email/phone/linkedin) *before* any field schema exists.
            # ATSAdapter.fill_fields instead needs an already-extracted
            # list[ApplicationField] + resolve_fields() answers, which are
            # only available further down this same branch — there is no
            # equivalent single adapter call for this earlier, schema-less
            # step, so it stays inline unchanged.
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

            # Task 3: extract every field (including radio groups and
            # selects — review_snapshot's own fields list is only used for
            # the submit-time fingerprint, not for answer resolution) and
            # resolve each against saved answers / structured profile data.
            # Delegated to the matched ATSAdapter — for every adapter today
            # this is the same FIELD_SNAPSHOT_JS/extract_fields pair that
            # used to be called inline here, but adapter-specific extraction
            # (e.g. Greenhouse/Lever fieldset grouping) now takes over for
            # free when one of those ATSes is detected.
            schema = await adapter.extract_fields(page)
            async with AsyncSessionLocal() as db:
                resolved = await resolve_fields(db, run.user_id, schema)
                await db.commit()
            resolved_by_id = {r.field_id: r for r in resolved}
            missing_required = [
                f for f in schema
                if f.required and f.visible and not f.disabled and is_empty(f)
                and resolved_by_id[f.field_id].source == "unresolved"
            ]

            # adapter.locate_submit() replaces the old inline
            # count()==1/visible/enabled checks against SUBMIT_NAME — same
            # check today, but lets a future adapter use its own button
            # text/selector instead.
            submit = await adapter.locate_submit(page)
            # adapter.validate() replaces the old per-input `value` check,
            # which let an unchecked required checkbox/radio pass because
            # its raw HTML value attribute was non-empty — validate_fields
            # (called by every adapter today) checks the normalized semantic
            # value instead.
            missing = bool(await adapter.validate(page, schema))
            ready = (
                submit is not None and not missing and pending.get("resume_uploaded", False)
                and not await page.locator('input[type="password"]:visible').count()
            )
            await save_account_state(session, context)
            if ready:
                next_type = "browser_review"
            elif missing_required:
                next_type = "application_answers_required"
            else:
                next_type = "browser_input"
            if ready and pending.get("attempt_id"):
                await mark_attempt_awaiting_approval(pending["attempt_id"])
            async with AsyncSessionLocal() as db:
                saved = await db.get(BrowserSession, session.id)
                if saved is None:
                    raise RuntimeError("Browser session expired; prepare a new application for review")
                saved.status = "review" if ready else "input"
                saved.review = snapshot
                await db.commit()

            if next_type == "application_answers_required":
                return checkpoint(
                    pending, next_type,
                    "Answer these questions once — approved answers are reused on later applications.",
                    session_id=str(session.id),
                    fields=[
                        {
                            "field_id": f.field_id,
                            "question_key": f.normalized_key or normalize_question(f.label),
                            "label": f.label, "required": f.required, "options": f.options,
                        }
                        for f in missing_required
                    ],
                )
            return checkpoint(
                pending, next_type,
                "Review the completed form and approve its final submission." if ready else
                "Open the browser to log in, handle verification, navigate to the form, or fill missing answers. Then continue preparation.",
                session_id=str(session.id), form=snapshot,
            )

        # This stage is created only by the locked, authenticated approval endpoint.
        # review_snapshot() (and its fingerprint) stay inline rather than
        # moving onto the ATSAdapter Protocol: GenericAdapter.extract_fields
        # doesn't produce a fingerprint, and adding one would mean changing
        # the Protocol (and every adapter implementing it) for a value only
        # this module needs — not worth the ripple for a parallel-owned file.
        expected = pending.get("form", {}).get("fingerprint")
        snapshot = await review_snapshot(page)
        if not expected or snapshot["fingerprint"] != expected:
            return checkpoint(pending, "browser_input", "The form changed. Prepare and review it again.", form=snapshot)
        _, digest = await load_resume(run.user_id, pending["pdf_document_id"])
        if digest != pending.get("resume_sha256"):
            raise ValueError("Resume changed after approval")
        # adapter.locate_submit() replaces the old inline SUBMIT_NAME lookup.
        submit = await adapter.locate_submit(page)
        if submit is None:
            return checkpoint(pending, "browser_input", "The submit control changed. Review the form again.", form=snapshot)
        # Never retry this click: timeout/disconnection afterward is an unknown outcome.
        #
        # Kept on the inline CONFIRMATION regex rather than
        # adapter.verify_confirmation(): that method is inconsistent across
        # the four adapters today — Greenhouse/Lever's wait up to 15s
        # internally, Ashby/Generic's check immediately with no wait — so
        # calling it here would either add an unwanted ~15s stall to every
        # normal (not-yet-submitted) Greenhouse/Lever approval, or drop the
        # wait Ashby/Generic never had. Fixing that inconsistency means
        # editing the adapter files, which are out of this file's scope.
        if await page.get_by_text(CONFIRMATION).count():
            return {"status": "failed", "result": {"outcome": "unknown", "message": "An existing confirmation was found; inspect the portal before applying again"}}

        # Atomic awaiting_approval -> submitting compare-and-swap. If another
        # concurrent caller already claimed this attempt (or it is no longer
        # awaiting approval for any other reason), do not touch the browser —
        # this is what makes the external click at-most-once.
        attempt_id = pending.get("attempt_id")
        if attempt_id:
            attempt = await claim_attempt_for_submit(attempt_id, expected)
            if attempt is None:
                return {"status": "completed", "result": {
                    "outcome": "duplicate_suppressed",
                    "message": "This application is already being submitted or was already submitted.",
                }}

        try:
            await submit.click(timeout=15000, no_wait_after=True)
        except Exception:
            if attempt_id:
                await mark_attempt_outcome_unknown(attempt_id, "Submit click failed or timed out")
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
            if attempt_id:
                await mark_attempt_outcome_unknown(attempt_id, "Confirmation could not be verified after submit")
            return {"status": "failed", "result": {
                "outcome": "unknown", "job_url": pending["job_url"],
                "message": "Submission was attempted but could not be confirmed. Check the portal before retrying.",
            }}
        await save_account_state(session, context)
        if attempt_id:
            await mark_attempt_verified(attempt_id, match.group(0), page.url)
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
