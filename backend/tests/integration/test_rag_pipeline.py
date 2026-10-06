"""
Run with: INTEGRATION=1 pytest tests/integration/test_rag_pipeline.py -v
Requires: real DATABASE_URL, model API key configured in DB.
"""

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="Integration tests require INTEGRATION=1 env var",
)


@pytest.mark.asyncio
async def test_ingest_and_retrieve_roundtrip(test_db, test_user, test_model_settings):
    from app.models.db import UserDocument
    from app.services.rag_service import ingest_document, retrieve

    document_id = uuid.uuid4()
    with test_db() as db:
        db.add(
            UserDocument(
                id=document_id,
                user_id=test_user.id,
                doc_type="resume",
                filename="roundtrip.txt",
                storage_path=f"{test_user.id}/{document_id}.txt",
            )
        )
        db.commit()
    text = "Experienced Python engineer with 5 years FastAPI, LangChain, PostgreSQL. Led team of 4."
    chunks_stored = ingest_document(
        str(test_user.id),
        "resume",
        text,
        {
            "user_id": str(test_user.id),
            "doc_type": "resume",
            "document_id": str(document_id),
        },
        test_model_settings,
    )
    assert chunks_stored >= 1

    results = retrieve(
        str(test_user.id),
        "resume",
        "Python engineer experience",
        test_model_settings,
        k=3,
    )
    assert len(results) >= 1
    assert "Python" in results[0].page_content

    with test_db() as db:
        db.delete(db.get(UserDocument, document_id))
        db.commit()
