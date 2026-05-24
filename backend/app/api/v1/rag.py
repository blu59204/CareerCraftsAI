import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.api.v1.deps import get_current_user, get_db
from app.models.db import User, UserDocument, UserModelSettings
from app.services.storage_service import upload_file, delete_file
from app.services.rag_service import extract_text, ingest_document

router = APIRouter(prefix="/rag", tags=["rag"])

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

    model_config = {"from_attributes": True}


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

    result = await db.execute(
        select(UserModelSettings).where(
            UserModelSettings.user_id == current_user.id,
            UserModelSettings.is_active == True,  # noqa: E712
        )
    )
    model_settings = result.scalar_one_or_none()

    embedded_at = None
    if model_settings:
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
    return doc


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
    delete_file(doc.storage_path)
    await db.delete(doc)
