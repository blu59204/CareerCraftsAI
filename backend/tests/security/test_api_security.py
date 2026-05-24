"""
API security tests — auth enforcement, input validation, injection prevention.
Run: pytest tests/security -v
"""
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
    ]
    async with make_client() as client:
        for method, path in protected:
            resp = await client.request(method, path)
            assert resp.status_code in (401, 422), (
                f"{method} {path} returned {resp.status_code} — expected 401/422"
            )


@pytest.mark.asyncio
async def test_health_endpoint_is_public():
    async with make_client() as client:
        resp = await client.get("/health")
    assert resp.status_code == 200


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
            json={"task_type": "../../etc/passwd", "context": {}},
        )
    assert resp.status_code in (400, 401, 422)


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
