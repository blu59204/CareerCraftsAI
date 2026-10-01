"""Owned resume/persona selection shared by API and Temporal search workers."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import ForeignKey, String, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.db import ResumePersona, UserDocument


class SearchDefault(Base):
    __tablename__ = "job_search_defaults"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(10))
    basis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))


async def resolve_basis(db, user_id: uuid.UUID, resume_id=None, persona_id=None):
    if resume_id and persona_id:
        raise HTTPException(status_code=422, detail="Choose a resume or persona, not both")
    explicit = bool(resume_id or persona_id)
    default = None
    if not explicit:
        default = await db.get(SearchDefault, user_id)
        if default:
            if default.kind == "persona":
                persona_id = default.basis_id
            else:
                resume_id = default.basis_id
    persona = None
    if persona_id:
        persona = (
            await db.execute(
                select(ResumePersona).where(
                    ResumePersona.id == uuid.UUID(str(persona_id)),
                    ResumePersona.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if persona is None or not persona.primary_resume_id:
            if explicit:
                raise HTTPException(status_code=404, detail="Persona or its resume is unavailable")
            if default:
                await db.delete(default)
                await db.flush()
            return await resolve_basis(db, user_id)
        resume_id = persona.primary_resume_id
    statement = select(UserDocument).where(
        UserDocument.user_id == user_id, UserDocument.doc_type == "resume"
    )
    if resume_id:
        statement = statement.where(UserDocument.id == uuid.UUID(str(resume_id)))
    else:
        statement = statement.order_by(
            UserDocument.is_primary.desc(), UserDocument.embedded_at.desc().nulls_last()
        ).limit(1)
    document = (await db.execute(statement)).scalar_one_or_none()
    if document is None and resume_id:
        if explicit:
            raise HTTPException(status_code=404, detail="Resume is unavailable")
        if default:
            await db.delete(default)
            await db.flush()
        return await resolve_basis(db, user_id)
    return document, persona


async def basis_text(
    user_id: str, resume_id=None, persona_id=None, query=""
) -> tuple[str, str | None]:
    from app.services.jobs_database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        document, persona = await resolve_basis(db, uuid.UUID(user_id), resume_id, persona_id)
        if document is None:
            return "", None
        text = (document.raw_text or "")[:24000]
        # Use the established provider/dimension collection, constrained to this
        # owned document. Old chunks without document metadata fall back only to
        # this document's raw text, never the user's other resumes.
        if query:
            try:
                import asyncio

                from app.models.db import UserModelSettings
                from app.services import rag_service

                model_settings = (
                    await db.execute(
                        select(UserModelSettings)
                        .where(
                            UserModelSettings.user_id == uuid.UUID(user_id),
                            UserModelSettings.is_active.is_(True),
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if model_settings:
                    embeddings = rag_service.get_embedding_model(model_settings)
                    store = rag_service.get_vector_store(
                        user_id,
                        "resume",
                        embeddings,
                        provider=rag_service.get_embedding_provider(model_settings),
                    )
                    chunks = await asyncio.to_thread(
                        store.similarity_search,
                        query,
                        k=8,
                        filter={"document_id": str(document.id)},
                    )
                    if chunks:
                        text = "\n".join(chunk.page_content for chunk in chunks)[:24000]
            except Exception as exc:
                import logging

                logging.getLogger(__name__).info(
                    "selected_resume_rag_unavailable", extra={"error_type": type(exc).__name__}
                )
        if persona:
            text += "\nPersona keywords: " + str(persona.target_keywords or [])[:2000]
        return text, str(document.id)
