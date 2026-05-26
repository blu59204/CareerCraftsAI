import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.models.db import User, UserDocument, UserModelSettings
from app.services.rag_service import extract_text, ingest_document
from app.services.storage_service import delete_file, upload_file

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
VALID_DOC_TYPES = {"resume", "jd", "cert", "portfolio", "cover_letter"}


class DocumentResponse(BaseModel):
    id: uuid.UUID
    doc_type: str
    filename: str
    is_primary: bool
    embedded_at: datetime | None
    ats_score: int | None = None
    ats_data: dict | None = None
    warning: str | None = None

    model_config = {"from_attributes": True}


async def _score_resume_background(doc_id: str, raw_text: str) -> None:
    """Compute ATS score asynchronously after resume upload."""
    try:
        from app.services.ats_service import compute_ats_score
        from app.core.database import AsyncSessionLocal

        # Background scoring without a JD uses a generic placeholder to get baseline scores
        generic_jd = (
            "We are looking for a professional with relevant experience, "
            "strong skills, education background, and good communication abilities. "
            "The ideal candidate should have project management capabilities and technical expertise."
        )
        result = compute_ats_score(raw_text, generic_jd)

        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(UserDocument).where(UserDocument.id == uuid.UUID(doc_id))
            )
            doc = res.scalar_one_or_none()
            if doc:
                doc.ats_score = result.composite_score
                doc.ats_data = {
                    "keyword_score": result.keyword_score,
                    "readability_score": result.readability_score,
                    "format_score": result.format_score,
                    "matched_keywords": result.matched_keywords,
                    "missing_keywords": result.missing_keywords,
                    "suggestions": result.suggestions,
                    "flesch_kincaid": result.flesch_kincaid,
                    "avg_sentence_length": result.avg_sentence_length,
                    "format_checks": result.format_checks,
                }
                await db.commit()
    except Exception as exc:
        logger.warning("Background ATS scoring failed for doc %s: %s", doc_id, exc)


router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    is_primary: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if doc_type not in VALID_DOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid doc_type. Must be one of: {VALID_DOC_TYPES}",
        )
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Only PDF, DOCX, and TXT files are supported",
        )

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large — max 10 MB")

    storage_path = upload_file(
        str(current_user.id),
        file.filename or "upload.bin",
        content,
        file.content_type or "application/octet-stream",
    )
    raw_text = extract_text(content, file.filename or "upload.bin")
    upload_warning: str | None = None
    if (file.filename or "").lower().endswith(".pdf") and len(raw_text.strip()) < 100:
        upload_warning = "Scanned or image-only PDF detected — text extraction yielded little content. Re-upload a text-based PDF for best results."

    result = await db.execute(
        select(UserModelSettings).where(
            UserModelSettings.user_id == current_user.id,
            UserModelSettings.is_active == True,  # noqa: E712
        )
    )
    model_settings = result.scalars().first()

    embedded_at = None
    if model_settings:
        try:
            ingest_document(
                str(current_user.id),
                doc_type,
                raw_text,
                {
                    "user_id": str(current_user.id),
                    "doc_type": doc_type,
                    "filename": file.filename or "",
                },
                model_settings,
            )
            embedded_at = datetime.now(timezone.utc)
        except Exception:
            # Embedding failed — document saved without vectors, can retry later
            embedded_at = None

    doc = UserDocument(
        user_id=current_user.id,
        doc_type=doc_type,
        filename=file.filename or "upload.bin",
        storage_path=storage_path,
        raw_text=raw_text,
        embedded_at=embedded_at,
        is_primary=is_primary,
    )
    db.add(doc)
    await db.flush()

    # Trigger ATS scoring in background for resumes
    if doc_type == "resume" and raw_text:
        asyncio.create_task(_score_resume_background(str(doc.id), raw_text))

    return DocumentResponse(
        id=doc.id,
        doc_type=doc.doc_type,
        filename=doc.filename,
        is_primary=doc.is_primary,
        embedded_at=doc.embedded_at,
        ats_score=doc.ats_score if hasattr(doc, "ats_score") else None,
        ats_data=doc.ats_data if hasattr(doc, "ats_data") else None,
        warning=upload_warning,
    )


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    doc_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(UserDocument).where(UserDocument.user_id == current_user.id)
    if doc_type:
        if doc_type not in VALID_DOC_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid doc_type. Must be one of: {VALID_DOC_TYPES}",
            )
        query = query.where(UserDocument.doc_type == doc_type)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/documents/{document_id}/ats", response_model=dict)
async def get_ats_score(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserDocument).where(
            UserDocument.id == document_id,
            UserDocument.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "ats_score": doc.ats_score,
        "ats_data": doc.ats_data,
    }


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserDocument).where(
            UserDocument.id == document_id,
            UserDocument.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    storage_path = doc.storage_path
    await db.delete(doc)
    await db.flush()
    try:
        delete_file(storage_path)
    except Exception as exc:
        logger.warning("Supabase file delete failed for %s (best-effort): %s", storage_path, exc)
