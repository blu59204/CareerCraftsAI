"""Finds and verifies a recruiter's email address before anything is sent.

Sources are tried from most to least trustworthy: an address written in the
posting itself, the finder APIs (Hunter, Apollo), guessed name patterns, then
role mailboxes like jobs@. Every candidate is run through a verifier
(ZeroBounce, NeverBounce or MillionVerifier) and the result decides what
happens next:

- valid: safe to send.
- risky (catch-all) or unknown: hold and ask the member.
- invalid: never sent.

With no verifier key configured nothing can be "valid", so everything is held
for the member rather than risking bounces that damage their Gmail reputation.
API keys come from the environment (the deployer's or member's own accounts);
nothing here signs up for anything.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import httpx

from app.core.config import settings
from app.services.email_finder_service import _company_to_domain, _generate_emails

logger = logging.getLogger(__name__)

VALID, RISKY, UNKNOWN, INVALID = "valid", "risky", "unknown", "invalid"
SEND, ASK, SKIP = "send", "ask", "skip"

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_NOT_A_PERSON = ("noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon")
_ROLE_MAILBOXES = ("jobs", "careers", "recruiting", "talent", "hr")
_MAX_VERIFICATIONS = 6  # verifier credits are the member's money
_TIMEOUT = httpx.Timeout(10.0)


@dataclass
class Contact:
    email: str
    source: str  # posting | hunter | apollo | pattern | role_mailbox
    verdict: str = UNKNOWN
    name: str = ""
    verified_by: str | None = None

    @property
    def action(self) -> str:
        return {VALID: SEND, INVALID: SKIP}.get(self.verdict, ASK)


@dataclass
class Lookup:
    best: Contact | None = None
    rejected: list[Contact] = field(default_factory=list)


def emails_in_text(text: str, domain: str | None = None) -> list[str]:
    """Addresses written in a posting, dropping no-reply senders. When the
    company domain is known, only its own addresses count."""
    found: list[str] = []
    for match in _EMAIL.findall(text or ""):
        address = match.lower().rstrip(".")
        if any(token in address.split("@")[0] for token in _NOT_A_PERSON):
            continue
        if domain and not address.endswith("@" + domain):
            continue
        if address not in found:
            found.append(address)
    return found


# ── verifiers ──────────────────────────────────────────────────────────────


def _zerobounce(status: str) -> str:
    status = (status or "").lower()
    if status == "valid":
        return VALID
    if status in ("catch-all", "catch_all"):
        return RISKY
    if status in ("invalid", "spamtrap", "abuse", "do_not_mail"):
        return INVALID
    return UNKNOWN


def _neverbounce(result: str) -> str:
    return {"valid": VALID, "catchall": RISKY, "invalid": INVALID, "disposable": INVALID}.get(
        (result or "").lower(), UNKNOWN
    )


def _millionverifier(result: str) -> str:
    return {"ok": VALID, "catch_all": RISKY, "invalid": INVALID, "disposable": INVALID}.get(
        (result or "").lower(), UNKNOWN
    )


async def _get_json(client: httpx.AsyncClient, provider: str, url: str, **kwargs) -> dict | None:
    try:
        response = await client.get(url, **kwargs)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        # The request URL carries the API key, so log the provider only.
        logger.warning("%s request failed: %s", provider, type(exc).__name__)
        return None
    return data if isinstance(data, dict) else None


async def verify_address(client: httpx.AsyncClient, email: str) -> tuple[str, str | None]:
    """(verdict, provider) from the first configured verifier that answers."""
    if settings.ZEROBOUNCE_API_KEY:
        data = await _get_json(
            client,
            "zerobounce",
            "https://api.zerobounce.net/v2/validate",
            params={"api_key": settings.ZEROBOUNCE_API_KEY, "email": email},
        )
        if data and "status" in data:
            return _zerobounce(data["status"]), "zerobounce"
    if settings.NEVERBOUNCE_API_KEY:
        data = await _get_json(
            client,
            "neverbounce",
            "https://api.neverbounce.com/v4/single/check",
            params={"key": settings.NEVERBOUNCE_API_KEY, "email": email},
        )
        if data and data.get("status") == "success":
            return _neverbounce(data.get("result", "")), "neverbounce"
    if settings.MILLIONVERIFIER_API_KEY:
        data = await _get_json(
            client,
            "millionverifier",
            "https://api.millionverifier.com/api/v3/",
            params={"api": settings.MILLIONVERIFIER_API_KEY, "email": email},
        )
        if data and "result" in data:
            return _millionverifier(data["result"]), "millionverifier"
    return UNKNOWN, None


# ── finders ────────────────────────────────────────────────────────────────


async def hunter_candidates(
    client: httpx.AsyncClient, domain: str, first: str = "", last: str = ""
) -> list[Contact]:
    if not settings.HUNTER_API_KEY:
        return []
    key = settings.HUNTER_API_KEY
    out: list[Contact] = []
    if first and last:
        data = await _get_json(
            client,
            "hunter",
            "https://api.hunter.io/v2/email-finder",
            params={"domain": domain, "first_name": first, "last_name": last, "api_key": key},
        )
        email = ((data or {}).get("data") or {}).get("email")
        if email:
            out.append(Contact(email.lower(), "hunter", name=f"{first} {last}".strip()))
    data = await _get_json(
        client,
        "hunter",
        "https://api.hunter.io/v2/domain-search",
        params={
            "domain": domain,
            "type": "personal",
            "department": "hr",
            "limit": 5,
            "api_key": key,
        },
    )
    for item in ((data or {}).get("data") or {}).get("emails") or []:
        if item.get("value"):
            name = f"{item.get('first_name') or ''} {item.get('last_name') or ''}".strip()
            out.append(Contact(item["value"].lower(), "hunter", name=name))
    return out


async def apollo_candidates(
    client: httpx.AsyncClient, domain: str, company: str, first: str = "", last: str = ""
) -> list[Contact]:
    if not settings.APOLLO_API_KEY or not (first and last):
        return []
    try:
        response = await client.post(
            "https://api.apollo.io/api/v1/people/match",
            headers={"X-Api-Key": settings.APOLLO_API_KEY},
            json={
                "first_name": first,
                "last_name": last,
                "domain": domain,
                "organization_name": company,
            },
        )
        response.raise_for_status()
        person = (response.json() or {}).get("person") or {}
    except Exception as exc:
        logger.warning("apollo request failed: %s", type(exc).__name__)
        return []
    if person.get("email"):
        return [Contact(person["email"].lower(), "apollo", name=f"{first} {last}")]
    return []


def pattern_candidates(domain: str, first: str, last: str) -> list[Contact]:
    if not (first and last):
        return []
    return [Contact(email, "pattern") for email, _ in _generate_emails(first, last, domain)[:4]]


def role_mailboxes(domain: str) -> list[Contact]:
    return [Contact(f"{box}@{domain}", "role_mailbox") for box in _ROLE_MAILBOXES]


# ── orchestration ──────────────────────────────────────────────────────────


async def find_recruiter_contact(
    company: str,
    *,
    domain: str | None = None,
    recruiter_name: str = "",
    posting_text: str = "",
    client: httpx.AsyncClient | None = None,
) -> Lookup:
    """The first verified-valid contact in source order, else the best held
    one. Invalid addresses are returned in `rejected`, never as `best`."""
    domain = domain or _company_to_domain(company)
    parts = recruiter_name.split()
    first, last = (parts[0], parts[-1]) if len(parts) >= 2 else ("", "")

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        queue: list[Contact] = [Contact(e, "posting") for e in emails_in_text(posting_text, domain)]
        queue += await hunter_candidates(client, domain, first, last)
        queue += await apollo_candidates(client, domain, company, first, last)
        queue += pattern_candidates(domain, first, last)
        queue += role_mailboxes(domain)

        lookup = Lookup()
        seen: set[str] = set()
        checked = 0
        for contact in queue:
            if contact.email in seen:
                continue
            seen.add(contact.email)
            if checked >= _MAX_VERIFICATIONS:
                break
            checked += 1
            contact.verdict, contact.verified_by = await verify_address(client, contact.email)
            if contact.action == SKIP:
                lookup.rejected.append(contact)
            elif contact.action == SEND:
                lookup.best = contact
                return lookup
            elif lookup.best is None:
                lookup.best = contact
        return lookup
    finally:
        if owns_client:
            await client.aclose()
