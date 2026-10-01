import httpx
import pytest

from app.core.config import settings
from app.services import recruiter_email as re_


def _client(routes: dict[str, dict]):
    """A client whose answers are keyed by URL host+path substring."""

    def handler(request: httpx.Request) -> httpx.Response:
        for needle, payload in routes.items():
            if needle in str(request.url):
                return httpx.Response(200, json=payload)
        return httpx.Response(404, json={})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch):
    for name in (
        "HUNTER_API_KEY",
        "APOLLO_API_KEY",
        "ZEROBOUNCE_API_KEY",
        "NEVERBOUNCE_API_KEY",
        "MILLIONVERIFIER_API_KEY",
    ):
        monkeypatch.setattr(settings, name, "")


def test_emails_in_posting_skip_noreply_and_other_domains():
    text = "Apply to jane.roe@acme.com or noreply@acme.com; cc bob@other.org"
    assert re_.emails_in_text(text, "acme.com") == ["jane.roe@acme.com"]
    assert re_.emails_in_text(text) == ["jane.roe@acme.com", "bob@other.org"]


@pytest.mark.parametrize(
    "mapper,raw,expected",
    [
        (re_._zerobounce, "valid", re_.VALID),
        (re_._zerobounce, "catch-all", re_.RISKY),
        (re_._zerobounce, "spamtrap", re_.INVALID),
        (re_._zerobounce, "weird", re_.UNKNOWN),
        (re_._neverbounce, "catchall", re_.RISKY),
        (re_._neverbounce, "disposable", re_.INVALID),
        (re_._millionverifier, "ok", re_.VALID),
        (re_._millionverifier, "error", re_.UNKNOWN),
    ],
)
def test_verifier_answers_map_to_one_vocabulary(mapper, raw, expected):
    assert mapper(raw) == expected


def test_only_valid_is_sent_invalid_is_skipped_everything_else_asks():
    actions = {
        v: re_.Contact("a@b.co", "posting", verdict=v).action
        for v in (re_.VALID, re_.RISKY, re_.UNKNOWN, re_.INVALID)
    }
    assert actions == {"valid": "send", "risky": "ask", "unknown": "ask", "invalid": "skip"}


@pytest.mark.asyncio
async def test_without_a_verifier_nothing_is_ever_sent_automatically():
    async with _client({}) as client:
        lookup = await re_.find_recruiter_contact(
            "Acme", domain="acme.com", posting_text="write jane@acme.com", client=client
        )
    assert lookup.best.email == "jane@acme.com"
    assert lookup.best.action == re_.ASK


@pytest.mark.asyncio
async def test_first_valid_address_in_source_order_wins(monkeypatch):
    monkeypatch.setattr(settings, "ZEROBOUNCE_API_KEY", "k")
    monkeypatch.setattr(settings, "HUNTER_API_KEY", "k")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "zerobounce" in url:
            status = "valid" if "hunter.person%40acme.com" in url else "invalid"
            return httpx.Response(200, json={"status": status})
        if "email-finder" in url:
            return httpx.Response(200, json={"data": {"email": "Hunter.Person@acme.com"}})
        return httpx.Response(200, json={"data": {"emails": []}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        lookup = await re_.find_recruiter_contact(
            "Acme",
            domain="acme.com",
            recruiter_name="Hunter Person",
            posting_text="mail old@acme.com",
            client=client,
        )
    assert lookup.best.email == "hunter.person@acme.com"
    assert lookup.best.source == "hunter" and lookup.best.verified_by == "zerobounce"
    assert [c.email for c in lookup.rejected] == ["old@acme.com"]


@pytest.mark.asyncio
async def test_verification_spend_is_capped(monkeypatch):
    monkeypatch.setattr(settings, "NEVERBOUNCE_API_KEY", "k")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"status": "success", "result": "invalid"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        lookup = await re_.find_recruiter_contact(
            "Acme", domain="acme.com", recruiter_name="Jane Roe", client=client
        )
    assert len(calls) == re_._MAX_VERIFICATIONS
    assert lookup.best is None and len(lookup.rejected) == re_._MAX_VERIFICATIONS


@pytest.mark.asyncio
async def test_failed_provider_is_logged_without_the_api_key(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ZEROBOUNCE_API_KEY", "secret-key-123")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        verdict = await re_.verify_address(client, "a@b.co")
    assert verdict == (re_.UNKNOWN, None)
    assert "secret-key-123" not in caplog.text
