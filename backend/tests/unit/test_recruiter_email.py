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


def test_employer_domain_comes_from_the_company_site_not_job_boards():
    assert re_.employer_domain("https://careers.acme.co.in/jobs/1", "") == "acme.co.in"
    assert re_.employer_domain("https://boards.greenhouse.io/acme/jobs/1", "") is None
    assert re_.employer_domain("https://jobs.peakxv.com/jobs/1", "") is None
    posting = "Send your CV to hr@acme.com or me@gmail.com. Also ask jane@acme.com"
    assert re_.employer_domain("https://www.linkedin.com/jobs/view/1", posting) == "acme.com"
    assert re_.employer_domain(None, "mail me@gmail.com") is None


def test_the_companys_own_address_format_is_inferred_and_tried_first():
    known = [
        re_.Contact("jane.roe@acme.com", "hunter", name="Jane Roe"),
        re_.Contact("bob.lee@acme.com", "hunter", name="Bob Lee"),
        re_.Contact("jobs@acme.com", "hunter"),
    ]
    assert re_.infer_pattern(known) == "{first}.{last}"
    guesses = re_.pattern_candidates("acme.com", "Ann", "Wu", "{f}{last}")
    assert guesses[0].email == "awu@acme.com"
    assert re_.infer_pattern([]) is None


@pytest.mark.asyncio
async def test_a_guessed_domain_never_counts_as_verified(monkeypatch):
    monkeypatch.setattr(settings, "ZEROBOUNCE_API_KEY", "key")
    client = _client({"zerobounce": {"status": "valid"}})
    guessed = await re_.find_recruiter_contact("Acme", client=client)
    assert guessed.best.verdict == "risky"  # held for the member
    confirmed = await re_.find_recruiter_contact(
        "Acme",
        domain="acme.com",
        domain_confirmed=True,
        client=_client({"zerobounce": {"status": "valid"}}),
    )
    assert confirmed.best.verdict == "valid"


@pytest.mark.asyncio
async def test_prospeo_and_findymail_are_inert_without_keys_and_read_their_answers(monkeypatch):
    client = _client({})
    assert await re_.prospeo_candidates(client, "acme.com", "Ann", "Wu") == []
    assert await re_.findymail_candidates(client, "acme.com", "Ann", "Wu") == []
    monkeypatch.setattr(settings, "PROSPEO_API_KEY", "k")
    monkeypatch.setattr(settings, "FINDYMAIL_API_KEY", "k")

    def handler(request: httpx.Request) -> httpx.Response:
        if "prospeo" in str(request.url):
            return httpx.Response(200, json={"response": {"email": "Ann.Wu@acme.com"}})
        return httpx.Response(200, json={"contact": {"email": "ann@acme.com"}})

    live = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert (await re_.prospeo_candidates(live, "acme.com", "Ann", "Wu"))[
        0
    ].email == "ann.wu@acme.com"
    assert (await re_.findymail_candidates(live, "acme.com", "Ann", "Wu"))[0].source == "findymail"


@pytest.mark.asyncio
async def test_company_pages_supply_published_addresses(monkeypatch):
    pages = {
        "https://acme.com/": "<a>hello@acme.com</a> noreply@acme.com",
        "https://acme.com/careers": "Write to careers@acme.com or x@other.org",
    }

    async def fake_get(url, **kwargs):
        if url not in pages:
            raise ValueError("blocked")
        return httpx.Response(200, text=pages[url], request=httpx.Request("GET", url))

    monkeypatch.setattr("app.services.public_http.public_get", fake_get)
    found = await re_.website_candidates("acme.com")
    assert [c.email for c in found] == ["hello@acme.com", "careers@acme.com"]
    assert {c.source for c in found} == {"website"}
