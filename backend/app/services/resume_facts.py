"""User-verified resume facts: contact details and fixes the user saved.

Sources, all typed by the user themselves (never model output):

- ``CandidateProfile`` — email / phone / city / country / profile links
- ``User`` — phone and LinkedIn URL from account settings
- ``CandidateAnswer(question_key="resume.facts")`` — values entered in the
  resume "Fix gaps" form (full employer names, dates, education, contact)

The login email is only ever offered as a *suggestion* for the form; it is
not put on a resume unless the user confirms it.
"""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import CandidateAnswer, CandidateProfile, User
from app.services.resume_structure import CONTACT_FIELDS, clean_field

FACTS_KEY = "resume.facts"
_MAX_FACT_ITEMS = 20
logger = logging.getLogger(__name__)


def _link(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"^(?:https?://)?(?:www\.)?", "", value.strip()).rstrip("/")


def verified_contact(
    profile: CandidateProfile | None, user: User | None, facts: dict | None,
) -> dict[str, str]:
    """Contact fields the user has explicitly entered somewhere."""
    saved = (facts or {}).get("contact") or {}
    p = profile
    location = ""
    if p is not None:
        location = ", ".join(x for x in (p.city, p.country or p.state) if x)
    contact = {
        "email": saved.get("email") or (p.email if p else "") or "",
        "phone": saved.get("phone") or (p.phone if p else "") or (user.phone if user else "") or "",
        "location": saved.get("location") or location,
        "linkedin": _link(saved.get("linkedin") or (p.linkedin_url if p else "")
                          or (user.linkedin_url if user else "")),
        "github": _link(saved.get("github") or (p.github_url if p else "")),
        "portfolio": _link(saved.get("portfolio") or (p.portfolio_url if p else "")),
    }
    return {k: clean_field(v, 200) for k, v in contact.items()}


def contact_suggestions(
    profile: CandidateProfile | None, user: User | None, facts: dict | None,
) -> dict[str, str]:
    """Pre-fill values for the fix form: verified contact + the login email."""
    contact = verified_contact(profile, user, facts)
    if not contact["email"] and user is not None and user.email:
        contact["email"] = user.email
    return contact


def merge_facts(
    facts: dict,
    *,
    contact: dict | None,
    experience: list[dict],
    education: list[dict],
) -> dict:
    """Fold newly submitted fixes into the saved facts (newest wins)."""
    merged = {
        "contact": dict(facts.get("contact") or {}),
        "experience": list(facts.get("experience") or []),
        "education": list(facts.get("education") or []),
    }
    for key, value in (contact or {}).items():
        if key in CONTACT_FIELDS and value is not None:
            merged["contact"][key] = clean_field(value, 200)

    def _key(item: dict, *fields: str) -> str:
        return "|".join((item.get(f) or "").casefold() for f in fields)

    for item in experience:
        exp_key = _key(item, "role", "employer_match")
        merged["experience"] = [
            e for e in merged["experience"] if _key(e, "role", "employer_match") != exp_key
        ] + [item]
    for item in education:
        edu_key = _key(item, "degree", "institution")
        merged["education"] = [
            e for e in merged["education"] if _key(e, "degree", "institution") != edu_key
        ] + [item]
    merged["experience"] = merged["experience"][-_MAX_FACT_ITEMS:]
    merged["education"] = merged["education"][-_MAX_FACT_ITEMS:]
    return merged


# ── async (API) ─────────────────────────────────────────────────────────────

async def load_facts_row(db: AsyncSession, user_id: uuid.UUID) -> CandidateAnswer | None:
    return (await db.execute(
        select(CandidateAnswer).where(
            CandidateAnswer.user_id == user_id,
            CandidateAnswer.question_key == FACTS_KEY,
        )
    )).scalar_one_or_none()


async def load_profile(db: AsyncSession, user_id: uuid.UUID) -> CandidateProfile | None:
    return (await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    )).scalar_one_or_none()


async def save_facts(db: AsyncSession, user_id: uuid.UUID, facts: dict) -> None:
    row = await load_facts_row(db, user_id)
    if row is None:
        db.add(CandidateAnswer(
            user_id=user_id,
            question_key=FACTS_KEY,
            normalized_question="Resume facts entered in the resume gap fixer",
            answer_type="json",
            answer=facts,
            source="user",
            confidence=1.0,
            approved_by_user=True,
        ))
    else:
        row.answer = facts
        row.approved_by_user = True
    await db.flush()


# ── sync (agent worker) ─────────────────────────────────────────────────────

def fetch_resume_facts_sync(user_id: str) -> tuple[dict[str, str], dict]:
    """(verified contact, saved facts) for the Resume Agent. Never raises."""
    from app.core.sync_db import _get_sync_factory, _to_uuid

    try:
        uid = _to_uuid(user_id)
        with _get_sync_factory()() as session:
            profile = session.execute(
                select(CandidateProfile).where(CandidateProfile.user_id == uid)
            ).scalar_one_or_none()
            user = session.execute(select(User).where(User.id == uid)).scalar_one_or_none()
            row = session.execute(
                select(CandidateAnswer).where(
                    CandidateAnswer.user_id == uid,
                    CandidateAnswer.question_key == FACTS_KEY,
                    CandidateAnswer.approved_by_user.is_(True),
                )
            ).scalar_one_or_none()
            facts = dict(row.answer or {}) if row else {}
            return verified_contact(profile, user, facts), facts
    except Exception as exc:  # noqa: BLE001 — facts are an enhancement, never a blocker
        logger.warning("Could not load resume facts for %s: %s", user_id, exc)
        return {}, {}
