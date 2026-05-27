"""
Run with: INTEGRATION=1 pytest tests/integration/test_rag_pipeline.py -v
Requires: real DATABASE_URL, SUPABASE_URL/keys, model API key configured in DB.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="Integration tests require INTEGRATION=1 env var",
)


@pytest.mark.asyncio
async def test_ingest_and_retrieve_roundtrip(test_db, test_user, test_model_settings):
    from app.services.rag_service import ingest_document, retrieve

    text = "Experienced Python engineer with 5 years FastAPI, LangChain, PostgreSQL. Led team of 4."
    chunks_stored = ingest_document(
        str(test_user.id),
        "resume",
        text,
        {"user_id": str(test_user.id), "doc_type": "resume"},
        test_model_settings,
    )
    assert chunks_stored >= 1

    results = retrieve(
        str(test_user.id), "resume", "Python engineer experience", test_model_settings, k=3
    )
    assert len(results) >= 1
    assert "Python" in results[0].page_content
