import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.resume_agent import resume_agent_node
from app.agents.state import AgentState
from app.api.v1.deps import get_current_user, get_db
from app.api.v1.run_utils import CLIENT_SAFE_AGENT_ERROR
from app.core.rate_limit import limiter
from app.models.db import AgentRun, User, UserDocument

router = APIRouter(prefix="/resume", tags=["resume"])
logger = logging.getLogger(__name__)


class OptimizeRequest(BaseModel):
    jd_text: str = Field(max_length=20000)
    template: Literal["modern", "classic", "technical"] = Field(default="modern")


class OptimizeResponse(BaseModel):
    run_id: str
    status: str
    template: str = "modern"
    pdf_available: bool = False
    pdf_document_id: str | None = None
    # Mirrors prompts/resume_prompt.OUTPUT_SCHEMA:
    resume_markdown: str | None = None
    summary: str | None = None
    ats_score: int | None = None
    keywords_matched: list[str] = Field(default_factory=list)
    keywords_missing: list[str] = Field(default_factory=list)
    changes_made: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # Deterministic audit (resume_structure.review_resume) + form pre-fill.
    review: dict | None = None
    contact_suggestions: dict[str, str] = Field(default_factory=dict)
    # The name the PDF prints (account full name); overrides the `# Name` line.
    display_name: str = ""


TemplateName = Literal["modern", "classic", "technical"]
_FIELD = 160
_DATE_FIELD = 40


class ContactFix(BaseModel):
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=120)
    linkedin: str | None = Field(default=None, max_length=200)
    github: str | None = Field(default=None, max_length=200)
    portfolio: str | None = Field(default=None, max_length=200)


class ExperienceFix(BaseModel):
    index: int = Field(ge=0, le=50)
    role: str | None = Field(default=None, max_length=_FIELD)
    employer: str | None = Field(default=None, max_length=_FIELD)
    location: str | None = Field(default=None, max_length=_FIELD)
    start: str | None = Field(default=None, max_length=_DATE_FIELD)
    end: str | None = Field(default=None, max_length=_DATE_FIELD)


class EducationFix(BaseModel):
    index: int | None = Field(default=None, ge=0, le=20)
    degree: str | None = Field(default=None, max_length=_FIELD)
    institution: str | None = Field(default=None, max_length=_FIELD)
    location: str | None = Field(default=None, max_length=_FIELD)
    start: str | None = Field(default=None, max_length=_DATE_FIELD)
    end: str | None = Field(default=None, max_length=_DATE_FIELD)
    details: str | None = Field(default=None, max_length=300)


class ResumeFixRequest(BaseModel):
    """User-supplied facts for a tailored resume. Every field is optional;
    ``resume_markdown`` replaces the whole text (manual edit) before the
    structured fixes are applied."""

    resume_markdown: str | None = Field(default=None, max_length=30000)
    template: TemplateName | None = None
    contact: ContactFix | None = None
    experience: list[ExperienceFix] = Field(
        default_factory=list, max_length=30, description="At most 30 experience fixes."
    )
    education: list[EducationFix] = Field(
        default_factory=list, max_length=10, description="At most 10 education entries."
    )
    remember: bool = True


class TailoredResumeResponse(BaseModel):
    """A tailored resume. ``document_id`` may differ from the one requested
    by /fix: a resume pinned by a pending application approval is saved as
    a new version instead of being edited."""

    document_id: str
    template: str
    resume_markdown: str
    summary: str | None = None
    ats_score: int | None = None
    keywords_matched: list[str] = Field(default_factory=list)
    keywords_missing: list[str] = Field(default_factory=list)
    changes_made: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    review: dict
    contact_suggestions: dict[str, str] = Field(default_factory=dict)
    display_name: str = ""


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
    agent_run.completed_at = datetime.now(UTC)
    pending = result_state.get("pending_action") or {}
    if pending:
        # Small DB footprint: ids + score only. No markdown, no binary.
        agent_run.output = {
            "type": pending.get("type", "resume_ready"),
            "pdf_document_id": pending.get("pdf_document_id"),
            "ats_score": pending.get("ats_score"),
        }

    if result_state["status"] in ("failed", "error"):
        logger.warning(
            "Resume optimize agent failed for run %s: %s", run_id, result_state.get("error")
        )
        raise HTTPException(status_code=500, detail=CLIENT_SAFE_AGENT_ERROR)

    suggestions = await _contact_suggestions(db, current_user)
    return OptimizeResponse(
        run_id=run_id,
        status=result_state["status"],
        template=payload.template,
        pdf_available=bool(pending.get("pdf_document_id")),
        pdf_document_id=pending.get("pdf_document_id"),
        resume_markdown=pending.get("resume_markdown"),
        summary=pending.get("summary"),
        ats_score=pending.get("ats_score"),
        keywords_matched=pending.get("keywords_matched", []),
        keywords_missing=pending.get("keywords_missing", []),
        changes_made=pending.get("changes_made", []),
        warnings=pending.get("warnings", []),
        review=pending.get("review"),
        contact_suggestions=suggestions,
        display_name=current_user.full_name or "",
    )


async def _contact_suggestions(db: AsyncSession, user: User) -> dict[str, str]:
    from app.services.resume_facts import contact_suggestions, load_facts_row, load_profile

    try:
        profile = await load_profile(db, user.id)
        row = await load_facts_row(db, user.id)
        return contact_suggestions(profile, user, dict(row.answer or {}) if row else {})
    except Exception:  # noqa: BLE001 — pre-fill is optional
        logger.warning("Could not load resume contact suggestions", exc_info=True)
        return {}


async def _get_tailored_doc(db: AsyncSession, document_id: str, user: User) -> UserDocument:
    try:
        doc_uuid = uuid.UUID(document_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Document not found") from None
    doc = (await db.execute(
        select(UserDocument).where(
            UserDocument.id == doc_uuid,
            UserDocument.user_id == user.id,
            UserDocument.doc_type == "resume_tailored",
        )
    )).scalar_one_or_none()
    if not doc or not doc.raw_text:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _tailored_response(
    doc: UserDocument, suggestions: dict[str, str], display_name: str = "",
) -> TailoredResumeResponse:
    from app.services.resume_structure import filter_resolved_warnings, review_resume

    data = doc.ats_data or {}
    review = review_resume(doc.raw_text or "")
    return TailoredResumeResponse(
        document_id=str(doc.id),
        template=data.get("template") or "modern",
        resume_markdown=doc.raw_text or "",
        summary=data.get("summary"),
        ats_score=doc.ats_score,
        keywords_matched=data.get("keywords_matched") or [],
        keywords_missing=data.get("keywords_missing") or [],
        changes_made=data.get("changes_made") or [],
        # ats_data keeps the model's original warnings; hide the ones the
        # current text has resolved (they come back if the gap reappears).
        warnings=filter_resolved_warnings(list(data.get("warnings") or []), review),
        review=review,
        contact_suggestions=suggestions,
        display_name=display_name,
    )


# Attempt states in which an application has pinned its resume PDF (by
# sha256, captured when the attempt is reserved) and still has to upload or
# submit it. Editing that PDF in place would make the approval fail.
_PINNING_ATTEMPT_STATES = ("preparing", "awaiting_approval", "submitting")


async def _pinned_by_pending_approval(db: AsyncSession, doc: UserDocument) -> bool:
    """Whether an in-flight application approval references this PDF.

    Two references exist: an ApplicationAttempt still in progress for a
    JobApplication whose resume_id is this document, and an agent run
    awaiting approval whose checkpoint recorded this document together with
    its resume_sha256 (browser review stage, or the auto-apply pipeline's
    ``actions_pending``).
    """
    from sqlalchemy import and_, or_

    from app.models.db import AgentRun, ApplicationAttempt, JobApplication

    attempt = (await db.execute(
        select(ApplicationAttempt.id)
        .join(JobApplication, JobApplication.id == ApplicationAttempt.job_application_id)
        .where(
            ApplicationAttempt.user_id == doc.user_id,
            JobApplication.resume_id == doc.id,
            ApplicationAttempt.state.in_(_PINNING_ATTEMPT_STATES),
        )
        .limit(1)
    )).scalar_one_or_none()
    if attempt is not None:
        return True
    doc_id = str(doc.id)
    run = (await db.execute(
        select(AgentRun.id)
        .where(
            AgentRun.user_id == doc.user_id,
            AgentRun.status == "awaiting_approval",
            or_(
                and_(
                    AgentRun.output.has_key("resume_sha256"),
                    AgentRun.output.contains({"pdf_document_id": doc_id}),
                ),
                AgentRun.output.contains({"actions_pending": [{"pdf_document_id": doc_id}]}),
            ),
        )
        .limit(1)
    )).scalar_one_or_none()
    return run is not None


_RENDER_ERROR = (
    "The resume could not be rendered as a PDF. Shorten very long lines and try again."
)


@router.get("/tailored/{document_id}", response_model=TailoredResumeResponse)
async def get_tailored_resume(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A saved tailored resume with its gap review, for re-opening and fixing."""
    doc = await _get_tailored_doc(db, document_id, current_user)
    return _tailored_response(
        doc, await _contact_suggestions(db, current_user), current_user.full_name or ""
    )


@router.post("/tailored/{document_id}/fix", response_model=TailoredResumeResponse)
@limiter.limit("30/minute")
async def fix_tailored_resume(
    request: Request,
    document_id: str,
    payload: ResumeFixRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply user-typed facts (contact, dates, employer, education) or a manual
    edit to a tailored resume, then re-render its PDF.

    No model call: the edit is deterministic and uses only what the user
    entered, so it cannot introduce invented content.

    The document is edited in place unless a pending application approval
    has pinned its PDF; then the fix is saved as a new document (the
    response carries its id) and the original is left untouched.
    """
    from app.services.ats_service import compute_ats_score
    from app.services.pdf_service import generate_resume_pdf
    from app.services.resume_facts import load_facts_row, merge_facts, save_facts
    from app.services.resume_structure import apply_fixes, clean_placeholders, review_resume
    from app.services.storage_service import delete_file, upload_file

    doc = await _get_tailored_doc(db, document_id, current_user)
    data = dict(doc.ats_data or {})
    template = payload.template or data.get("template") or "modern"
    base = clean_placeholders(
        payload.resume_markdown if payload.resume_markdown is not None else doc.raw_text or ""
    )
    # Check before apply_fixes: it re-inserts the name heading, so a blanked
    # manual edit would otherwise save a resume containing only the name.
    if not base.strip():
        raise HTTPException(status_code=422, detail="Resume text cannot be empty")
    # Fix indices refer to this text (the manual edit, when one was sent).
    before = review_resume(base)

    contact = payload.contact.model_dump(exclude_unset=True) if payload.contact else None
    experience = [f.model_dump(exclude_unset=True) for f in payload.experience]
    education = [f.model_dump(exclude_unset=True) for f in payload.education]
    try:
        markdown = apply_fixes(
            base,
            full_name=current_user.full_name or "",
            contact=contact,
            experience=experience,
            education=education,
        )
    except ValueError as exc:
        # Our own messages (e.g. "No experience entry at index 5").
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if not markdown.strip():
        raise HTTPException(status_code=422, detail="Resume text cannot be empty")

    try:
        pdf_bytes = await asyncio.to_thread(
            generate_resume_pdf, markdown,
            full_name=current_user.full_name or "", template=template,
        )
    except Exception:  # noqa: BLE001 — ValueError, LayoutError, any ReportLab failure
        # The real message can carry ReportLab markup and internals: log it only.
        logger.exception("Resume PDF render failed for document %s", doc.id)
        raise HTTPException(status_code=422, detail=_RENDER_ERROR) from None

    # Score before uploading so a scoring failure cannot orphan a new file.
    ats_score = doc.ats_score
    jd_text = data.get("jd_text") or ""
    if jd_text:
        ats = await asyncio.to_thread(compute_ats_score, markdown, jd_text)
        ats_score = ats.composite_score
        data["keywords_missing"] = list(ats.missing_keywords[:10])
    review = review_resume(markdown)
    # data["warnings"] stays the model's original list; it is filtered when read.
    data["template"] = template
    pinned = await _pinned_by_pending_approval(db, doc)

    new_path = upload_file(str(current_user.id), "resume.pdf", pdf_bytes, "application/pdf")
    old_path = doc.storage_path
    try:
        if pinned:
            target = UserDocument(
                id=uuid.uuid4(),
                user_id=doc.user_id,
                doc_type=doc.doc_type,
                filename=doc.filename,
                storage_path=new_path,
                raw_text=markdown,
                ats_score=ats_score,
                ats_data=data,
            )
            db.add(target)
        else:
            target = doc
            doc.raw_text = markdown
            doc.storage_path = new_path
            doc.ats_score = ats_score
            doc.ats_data = data

        if payload.remember:
            row = await load_facts_row(db, current_user.id)
            facts = merge_facts(
                dict(row.answer or {}) if row else {},
                contact=contact,
                experience=_experience_facts(experience, before, review),
                education=[
                    {k: v for k, v in e.items() if k != "index" and v}
                    for e in education if e.get("index") is None
                ],
            )
            await save_facts(db, current_user.id, facts)
        await db.flush()
        # Commit here, not in get_db after the response: the old PDF may only
        # be deleted once the row pointing at the new one is durable.
        await db.commit()
    except Exception:
        try:
            delete_file(new_path, str(current_user.id))
        except Exception:  # noqa: BLE001
            logger.warning("Could not clean up resume PDF %s", new_path)
        raise

    if not pinned and old_path and old_path != new_path:
        try:
            delete_file(old_path, str(current_user.id))
        except Exception:  # noqa: BLE001 — a stale file is harmless
            logger.warning("Could not delete superseded resume PDF %s", old_path)

    return _tailored_response(
        target, await _contact_suggestions(db, current_user), current_user.full_name or ""
    )


def _experience_facts(fixes: list[dict], before: dict, after: dict) -> list[dict]:
    """Saved-fact records for experience fixes.

    Only the keys the user submitted (non-empty) are facts, listed in
    ``submitted``. ``role``/``employer_match`` let apply_saved_facts find the
    entry in a later draft and ``match_role``/``match_employer`` record the
    entry as it was before this fix; they may be model-written text and are
    never presented as facts.
    """
    from app.services.resume_facts import EXPERIENCE_FACT_KEYS

    old = {e["index"]: e for e in before.get("experience", [])}
    new = {e["index"]: e for e in after.get("experience", [])}
    facts = []
    for fix in fixes:
        idx = fix["index"]
        if idx not in new:
            continue
        entry, original = new[idx], old.get(idx, new[idx])
        submitted = [k for k in EXPERIENCE_FACT_KEYS if (fix.get(k) or "").strip()]
        if not submitted:
            continue
        record = {
            "role": entry["role"],
            "employer_match": original["employer"] or entry["employer"],
            "match_role": original["role"] or entry["role"],
            "match_employer": original["employer"],
            "submitted": submitted,
        }
        # The value as it now stands in the resume (normalised by apply_fixes).
        record.update({k: entry[k] or fix[k] for k in submitted})
        facts.append(record)
    return facts


@router.get("/download/{document_id}")
async def download_pdf(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.storage_service import download_file

    try:
        doc_uuid = uuid.UUID(document_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Document not found") from None
    result = await db.execute(
        select(UserDocument).where(
            UserDocument.id == doc_uuid,
            UserDocument.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    pdf_bytes = None
    # Re-render tailored resumes so they pick up template improvements, but only
    # when the chosen template was recorded. Older documents did not store it;
    # re-rendering them would silently switch a Classic/Technical resume to
    # Modern, so they keep the PDF that was generated at the time.
    template = (doc.ats_data or {}).get("template")
    if (
        doc.doc_type == "resume_tailored"
        and doc.raw_text
        and template in ("modern", "classic", "technical")
    ):
        from app.services.pdf_service import generate_resume_pdf

        try:
            # ReportLab is CPU-bound; keep it off the event loop.
            pdf_bytes = await asyncio.to_thread(
                generate_resume_pdf,
                doc.raw_text,
                full_name=current_user.full_name or "",
                template=template,
            )
        except Exception:
            logger.exception(
                "Resume re-render failed for document %s; serving stored PDF", document_id
            )
    if pdf_bytes is None:
        try:
            pdf_bytes = download_file(doc.storage_path, str(current_user.id))
        except PermissionError:
            raise HTTPException(status_code=404, detail="Document not found") from None
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail="Storage download failed") from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=resume_{document_id[:8]}.pdf"
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


async def _verify_resume_ownership(db: AsyncSession, resume_id, user_id) -> None:
    """Ensure a referenced resume document belongs to the user (prevents IDOR)."""
    if resume_id is None:
        return
    from app.models.db import UserDocument

    result = await db.execute(
        select(UserDocument.id).where(
            UserDocument.id == resume_id,
            UserDocument.user_id == user_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Resume document not found")


@router.post("/personas", status_code=201)
async def create_persona(
    body: PersonaCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func

    from app.models.db import ResumePersona

    # Enforce max 10 (use COUNT, not len() of all rows)
    count_result = await db.execute(
        select(func.count(ResumePersona.id)).where(ResumePersona.user_id == current_user.id)
    )
    if (count_result.scalar_one() or 0) >= 10:
        raise HTTPException(status_code=400, detail="Maximum 10 personas allowed")

    # Prevent attaching another user's resume document
    await _verify_resume_ownership(db, body.primary_resume_id, current_user.id)

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
        await _verify_resume_ownership(db, body.primary_resume_id, current_user.id)
        persona.primary_resume_id = body.primary_resume_id
    return persona


@router.delete("/personas/{persona_id}", status_code=204)
async def delete_persona(
    persona_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import delete

    from app.models.db import ResumePersona

    result = await db.execute(
        delete(ResumePersona).where(
            ResumePersona.id == persona_id,
            ResumePersona.user_id == current_user.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Persona not found")
