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
from sqlalchemy.exc import IntegrityError
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
    profile: CandidateProfile | None,
    user: User | None,
    facts: dict | None,
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
        "linkedin": _link(
            saved.get("linkedin")
            or (p.linkedin_url if p else "")
            or (user.linkedin_url if user else "")
        ),
        "github": _link(saved.get("github") or (p.github_url if p else "")),
        "portfolio": _link(saved.get("portfolio") or (p.portfolio_url if p else "")),
    }
    return {k: clean_field(v, 200) for k, v in contact.items()}


def contact_suggestions(
    profile: CandidateProfile | None,
    user: User | None,
    facts: dict | None,
) -> dict[str, str]:
    """Pre-fill values for the fix form: verified contact + the login email."""
    contact = verified_contact(profile, user, facts)
    if not contact["email"] and user is not None and user.email:
        contact["email"] = user.email
    return contact


# Experience fact records. Only the keys listed in ``submitted`` were typed
# by the user; ``role``/``employer_match`` (read by apply_saved_facts) and
# ``match_role``/``match_employer`` only locate the entry in a later draft and
# may hold model-written text, so they are never presented as facts. Records
# saved before ``submitted`` existed are read as legacy (see resume_prompt).
EXPERIENCE_FACT_KEYS = ("role", "employer", "location", "start", "end")
_EXPERIENCE_MATCH_KEYS = ("employer_match", "match_role", "match_employer")
_EDUCATION_FACT_KEYS = ("degree", "institution", "location", "start", "end", "details")


def _field_limit(key: str) -> int:
    return {"start": 40, "end": 40, "details": 300}.get(key, 160)


def _clean_record(item: dict, keys: tuple[str, ...]) -> dict:
    """Keep only known keys, each normalised to one safe line."""
    out = {}
    for key in keys:
        value = clean_field(item.get(key), _field_limit(key))
        if value:
            out[key] = value
    return out


def _clean_experience(item: dict) -> dict:
    out = _clean_record(item, EXPERIENCE_FACT_KEYS + _EXPERIENCE_MATCH_KEYS)
    if "submitted" in item:
        typed = set(item.get("submitted") or [])
        out["submitted"] = [k for k in EXPERIENCE_FACT_KEYS if k in typed and k in out]
    return out


def _fold(value: str | None) -> str:
    return (value or "").casefold()


def _same_experience(old: dict, new: dict) -> bool:
    """Whether a new experience fact is about the same entry as a saved one.

    The new record's match keys describe the entry *before* this fix, which
    may already carry values from an earlier fix (e.g. the full employer).
    """
    old_roles = {_fold(old.get("role")), _fold(old.get("match_role"))} - {""}
    new_roles = {_fold(new.get("role")), _fold(new.get("match_role"))} - {""}
    role_hit = bool(old_roles & new_roles) or not (old_roles or new_roles)
    employers = {_fold(old.get("employer_match")), _fold(old.get("employer"))}
    return role_hit and _fold(new.get("employer_match")) in employers


def _merge_experience(saved: list[dict], item: dict) -> list[dict]:
    for pos, old in enumerate(saved):
        if not _same_experience(old, item):
            continue
        if "submitted" not in old:
            # Legacy record: its values may be model-written; replace it.
            return [*saved[:pos], *saved[pos + 1 :], item]
        combined = {**old, **{k: v for k, v in item.items() if k != "submitted"}}
        # Keep the oldest locator: it is the text a fresh draft will contain.
        for key in _EXPERIENCE_MATCH_KEYS:
            if old.get(key):
                combined[key] = old[key]
        typed = set(old["submitted"]) | set(item.get("submitted") or [])
        combined["submitted"] = [k for k in EXPERIENCE_FACT_KEYS if k in typed]
        return [*saved[:pos], *saved[pos + 1 :], combined]
    return [*saved, item]


def merge_facts(
    facts: dict,
    *,
    contact: dict | None,
    experience: list[dict],
    education: list[dict],
) -> dict:
    """Fold newly submitted fixes into the saved facts (newest wins).

    Every value is normalised with clean_field (one line, no ``|``), so a
    saved fact can never break the resume Markdown or the prompt fences.
    """
    merged = {
        "contact": {
            k: clean_field(v, 200)
            for k, v in (facts.get("contact") or {}).items()
            if k in CONTACT_FIELDS and clean_field(v, 200)
        },
        "experience": [
            e for e in (_clean_experience(x) for x in facts.get("experience") or []) if e
        ],
        "education": [
            e
            for e in (_clean_record(x, _EDUCATION_FACT_KEYS) for x in facts.get("education") or [])
            if e
        ],
    }
    for key, value in (contact or {}).items():
        if key in CONTACT_FIELDS and value is not None:
            merged["contact"][key] = clean_field(value, 200)

    for item in experience:
        cleaned = _clean_experience(item)
        if cleaned.get("submitted") or ("submitted" not in cleaned and cleaned):
            merged["experience"] = _merge_experience(merged["experience"], cleaned)

    def _key(item: dict, *fields: str) -> str:
        return "|".join(_fold(item.get(f)) for f in fields)

    for item in education:
        cleaned = _clean_record(item, _EDUCATION_FACT_KEYS)
        if not cleaned:
            continue
        edu_key = _key(cleaned, "degree", "institution")
        merged["education"] = [
            e for e in merged["education"] if _key(e, "degree", "institution") != edu_key
        ] + [cleaned]
    merged["experience"] = merged["experience"][-_MAX_FACT_ITEMS:]
    merged["education"] = merged["education"][-_MAX_FACT_ITEMS:]
    return merged


# ── async (API) ─────────────────────────────────────────────────────────────


async def load_facts_row(db: AsyncSession, user_id: uuid.UUID) -> CandidateAnswer | None:
    return (
        await db.execute(
            select(CandidateAnswer).where(
                CandidateAnswer.user_id == user_id,
                CandidateAnswer.question_key == FACTS_KEY,
            )
        )
    ).scalar_one_or_none()


async def load_profile(db: AsyncSession, user_id: uuid.UUID) -> CandidateProfile | None:
    return (
        await db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    ).scalar_one_or_none()


async def save_facts(db: AsyncSession, user_id: uuid.UUID, facts: dict) -> None:
    row = await load_facts_row(db, user_id)
    if row is None:
        try:
            # Savepoint: a concurrent first save for the same user hits the
            # unique (user_id, question_key) constraint; only this insert is
            # rolled back and the winner's row is updated below instead.
            async with db.begin_nested():
                db.add(
                    CandidateAnswer(
                        user_id=user_id,
                        question_key=FACTS_KEY,
                        normalized_question="Resume facts entered in the resume gap fixer",
                        answer_type="json",
                        answer=facts,
                        source="user",
                        confidence=1.0,
                        approved_by_user=True,
                    )
                )
                await db.flush()
            return
        except IntegrityError:
            row = await load_facts_row(db, user_id)
            if row is None:
                raise
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
