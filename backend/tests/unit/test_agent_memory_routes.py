from fastapi.testclient import TestClient


def test_memory_routes_require_sign_in():
    from app.main import app

    client = TestClient(app)
    assert client.get("/api/v1/memory").status_code in (401, 403)
    assert client.delete("/api/v1/memory").status_code in (401, 403)
    assert client.delete("/api/v1/memory/learnings/1").status_code in (401, 403)


def test_outreach_routes_require_sign_in():
    from app.main import app

    client = TestClient(app)
    assert client.get("/api/v1/outreach").status_code in (401, 403)
    assert client.post("/api/v1/outreach/abc/approve").status_code in (401, 403)
    assert client.patch("/api/v1/outreach/abc", json={"body": "x"}).status_code in (401, 403)
