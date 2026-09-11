"""
Integration smoke tests — requires a running stack.
Set INTEGRATION=1 to enable. All tests skip when env var is missing.

Usage:
    INTEGRATION=1 pytest tests/integration/ -v
"""
import os
import sys
import time
import uuid

import pytest
import httpx

INTEGRATION = os.environ.get("INTEGRATION") == "1"

pytestmark = pytest.mark.skipif(not INTEGRATION, reason="INTEGRATION=1 not set")

BACKEND = os.environ.get("TEST_BACKEND_URL", "http://localhost:8000")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")


@pytest.fixture(scope="module")
def http():
    with httpx.Client(base_url=BACKEND, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="module")
async def async_http():
    async with httpx.AsyncClient(base_url=BACKEND, timeout=120.0) as client:
        yield client


class TestHealthCheck:
    def test_health_endpoint(self, http):
        resp = http.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["db"] == "ok"
        assert data["redis"] == "ok"


class TestAuthFlow:
    def test_register_and_login_via_supabase(self):
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            pytest.skip("Supabase URL/key not configured")
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        email = f"smoke-{uuid.uuid4().hex[:8]}@test.com"
        resp = client.auth.sign_up({"email": email, "password": "SmokeTest123!"})
        assert resp.user is not None
        session = resp.session
        if session is None:
            resp2 = client.auth.sign_in_with_password({"email": email, "password": "SmokeTest123!"})
            session = resp2.session
        assert session is not None
        assert session.access_token is not None

        # Verify backend accepts the JWT
        backend_resp = httpx.get(
            f"{BACKEND}/api/v1/users/me",
            headers={"Authorization": f"Bearer {session.access_token}"},
        )
        assert backend_resp.status_code == 200
        user_data = backend_resp.json()
        assert "email" in user_data or "id" in user_data


class TestRAGIngestion:
    def test_upload_pdf_resume(self, http):
        pytest.skip("Requires authenticated user — run manually with valid JWT")


class TestAgentRun:
    def test_run_resume_agent(self, http):
        pytest.skip("Requires authenticated user — run manually with valid JWT")

    def test_sse_stream_connection(self):
        pytest.skip("Requires authenticated user and active run_id — run manually")


class TestPDFGeneration:
    def test_pdf_resume_generation(self):
        from app.services.pdf_service import generate_resume_pdf
        text = "John Doe\n\nSUMMARY\nPython engineer\n\nEXPERIENCE\nBuilt APIs"
        pdf = generate_resume_pdf(text, full_name="John Doe", template="modern")
        assert pdf is not None
        assert len(pdf) > 100
        assert pdf[:4] == b"%PDF"


class TestDatabaseConnection:
    @pytest.mark.asyncio
    async def test_db_select_one_works(self):
        from app.core.database import async_engine
        try:
            async with async_engine.begin() as conn:
                result = await conn.execute("SELECT 1")
                assert result is not None
        except Exception as e:
            pytest.fail(f"Database connection failed: {e}")


class TestRedisConnection:
    @pytest.mark.asyncio
    async def test_redis_ping_works(self):
        import redis.asyncio as aioredis
        from app.core.config import settings
        try:
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await r.ping()
            await r.aclose()
        except Exception as e:
            pytest.fail(f"Redis connection failed: {e}")


class TestFullWorkflow:
    @pytest.mark.asyncio
    async def test_full_resume_tailoring_workflow(self):
        pytest.skip("End-to-end workflow requires full authenticated session — run manually")
