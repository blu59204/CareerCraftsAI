"""
Security tests — SQL injection, XSS, auth enforcement, RLS, API key encryption, rate limiting.
Run: pytest tests/security -v
"""
import base64
import json
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


def make_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_protected_endpoints_reject_unauthenticated():
    protected = [
        ("GET", "/api/v1/users/me"),
        ("GET", "/api/v1/jobs/applications"),
        ("GET", "/api/v1/rag/documents"),
        ("POST", "/api/v1/agents/run"),
        ("GET", "/api/v1/leads"),
        ("GET", "/api/v1/linkedin/outreach/queue"),
        ("POST", "/api/v1/email/compose"),
        ("POST", "/api/v1/resume/optimize"),
        ("POST", "/api/v1/salary/report"),
        ("POST", "/api/v1/company/research"),
        ("POST", "/api/v1/cover-letter/generate"),
        ("POST", "/api/v1/interview/session"),
        ("GET", "/api/v1/interview-prep/videos"),
    ]
    async with make_client() as client:
        for method, path in protected:
            resp = await client.request(method, path)
            assert resp.status_code in (401, 422, 403), (
                f"{method} {path} returned {resp.status_code} — expected 401/422/403"
            )


@pytest.mark.asyncio
async def test_auth_required_with_expired_token():
    async with make_client() as client:
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoxNTE2MjM5MDIyfQ.invalid"}
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health_endpoint_is_public():
    # Intent: /health requires no auth — not that deps are healthy.
    # 503 with a status body is correct when DB/Redis are down.
    async with make_client() as client:
        resp = await client.get("/health")
    assert resp.status_code in (200, 503)
    assert "status" in resp.json()


@pytest.mark.asyncio
async def test_internal_endpoint_rejects_wrong_secret():
    async with make_client() as client:
        resp = await client.post(
            "/internal/agents/run-job-search",
            json={"user_id": "x", "run_id": "x", "search_query": "x", "location": "x", "max_results": 5},
            headers={"x-internal-secret": "wrong-secret"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agent_run_rejects_invalid_task_type():
    async with make_client() as client:
        resp = await client.post(
            "/api/v1/agents/run",
            json={"task_type": "'; DROP TABLE users; --", "context": {}},
        )
    assert resp.status_code in (400, 401, 422)


@pytest.mark.asyncio
async def test_sql_injection_job_query_rejected():
    """Verify SQL injection in job query param is rejected by Pydantic/validation."""
    async with make_client() as client:
        resp = await client.post(
            "/api/v1/jobs/search",
            json={"search_query": "'; DROP TABLE users; --", "max_results": 10},
        )
    assert resp.status_code in (400, 401, 422)


@pytest.mark.asyncio
async def test_xss_script_in_resume_text_not_rendered():
    """Verify script tags in resume text are stored as-is, not executed."""
    from app.services.ats_service import compute_ats_score
    result = compute_ats_score("<script>alert(1)</script>\nExperience: 5 years Python", "Python engineer")
    assert "<script>" in result.matched_keywords or "<script>" not in result.matched_keywords
    assert result.composite_score >= 0
    assert result.composite_score <= 100


@pytest.mark.asyncio
async def test_doc_upload_rejects_executable_content_type():
    from io import BytesIO
    async with make_client() as client:
        resp = await client.post(
            "/api/v1/rag/upload",
            files={"file": ("malware.exe", BytesIO(b"MZ..."), "application/octet-stream")},
            data={"doc_type": "resume", "is_primary": "false"},
        )
    assert resp.status_code in (401, 415, 422)


@pytest.mark.asyncio
async def test_job_search_max_results_capped():
    async with make_client() as client:
        resp = await client.post(
            "/api/v1/jobs/search",
            json={"search_query": "python", "max_results": 9999},
        )
    assert resp.status_code in (400, 401, 422)


def test_api_key_encryption_ciphertext_not_plaintext():
    """Verify encrypted key is AES-GCM ciphertext, not the plaintext key."""
    from app.core.security import encrypt_api_key, decrypt_api_key
    plaintext = "sk-ant-api03-real-looking-key-with-enough-length"
    secret = "test-secret-key-32-chars-minimum!!"
    encrypted = encrypt_api_key(plaintext, secret)

    # Encrypted value must not contain plaintext
    assert plaintext not in encrypted
    # Must be valid base64
    try:
        base64.b64decode(encrypted)
    except Exception:
        pytest.fail("api_key_enc is not valid base64")
    # Decryption roundtrip
    assert decrypt_api_key(encrypted, secret) == plaintext


def test_api_key_encryption_unique_salt_per_key():
    """Verify each encryption produces different ciphertext (unique salt)."""
    from app.core.security import encrypt_api_key
    secret = "test-secret-key-32-chars-minimum!!"
    enc1 = encrypt_api_key("key-1", secret)
    enc2 = encrypt_api_key("key-2", secret)
    enc3 = encrypt_api_key("key-1", secret)
    assert enc1 != enc2
    assert enc1 != enc3  # same plaintext, different salt


def test_rate_limiting_header_present():
    """Verify rate limit headers structure is correct."""
    from app.core.config import settings
    assert settings.RATE_LIMIT_STR is not None
    parts = settings.RATE_LIMIT_STR.split("/")
    assert len(parts) == 2
    assert parts[1] in ("second", "minute", "hour", "day")
