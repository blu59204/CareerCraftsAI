import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.api.v1.run_utils import apply_harness_result
from app.core.rate_limit import limiter
from app.models.db import AgentRun, JobApplication, User, UserDocument, UserPreferences
from app.schemas.jobs import JobSearchQuerySchema
from app.services.queue_service import enqueue_job_search

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)

NL_SEARCH_TIMEOUT_SECONDS = 120
VALID_STATUSES = {"saved", "applied", "viewed", "interview", "offer", "rejected"}


class JobSearchRequest(JobSearchQuerySchema):
    search_query: str = Field(default="", max_length=200)
    location: str = "Remote"
    max_results: int = 10
    # Default to False: the free keyless job-board APIs (Remotive / Arbeitnow
    # / Jobicy) and JobSpy are fast and return real apply links. live_browser
    # opens a visible Chromium for the demo, but it triggers CAPTCHAs and
    # frequently returns zero jobs. Flip on explicitly via the UI.
    live_browser: bool = False
    work_mode: str | None = None
    experience_level: str | None = None
    years_experience: int | None = Field(None, ge=0, le=60)
    job_type: str | None = None
    target_roles: list[str] | None = None
    preferred_locations: list[str] | None = None


class JobSearchResponse(BaseModel):
    run_id: str
    queue_job_id: str
    status: str = "queued"
    queued: bool = True


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    company: str
    role: str
    location: str | None
    job_url: str | None
    match_score: int | None
    status: str
    applied_at: datetime | None

    model_config = {"from_attributes": True}


class JobSearchProfileResponse(BaseModel):
    resume_found: bool
    resume_id: uuid.UUID | None = None
    resume_filename: str | None = None
    role_suggestions: list[str] = []
    skills: list[str] = []
    inferred_years_experience: int | None = None
    inferred_experience_level: str | None = None
    saved_preferences: dict = {}
    search_query_preview: str
    location_preview: str
    work_mode_preview: str | None = None
    missing_fields: list[str] = []
    analysis_notes: list[str] = []


class StatusUpdateBody(BaseModel):
    status: str


class PrepareApplyBody(BaseModel):
    live_browser: bool = False


class NLSearchRequest(BaseModel):
    query: str = Field(min_length=5, max_length=500)

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        import re
        v = v.replace("\x00", "")
        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", v)
        return v[:500]


def is_example_job_url(job_url: str | None) -> bool:
    if not job_url:
        return False
    hostname = urlparse(job_url).hostname or ""
    return hostname == "example.com" or hostname.endswith(".example.com")


def _matches_location_filter(app: JobApplication, location_filter: str | None) -> bool:
    if not location_filter:
        return True
    filters = {
        item.strip().lower()
        for item in location_filter.split(",")
        if item.strip()
    }
    if not filters:
        return True
    location = (app.location or "").lower()
    if not location:
        return False

    mode_filters = filters & {"remote", "hybrid", "onsite"}
    if "remote" in mode_filters and "remote" not in location:
        return False
    if "hybrid" in mode_filters and "hybrid" not in location:
        return False
    if "onsite" in mode_filters and "remote" in location:
        return False

    city_filters = filters - {"remote", "hybrid", "onsite"}
    if city_filters and not any(city in location for city in city_filters):
        return False

    return True


def _split_pref_values(value: str | None) -> list[str]:
    return [
        item.strip().lower()
        for item in (value or "").split(",")
        if item.strip()
    ]


ROLE_HINTS = (
    "frontend engineer",
    "backend engineer",
    "full stack engineer",
    "full-stack developer",
    "software engineer",
    "python developer",
    "react developer",
    "data analyst",
    "data scientist",
    "machine learning engineer",
    "devops engineer",
    "qa engineer",
    "product manager",
    "ui ux designer",
)

SKILL_HINTS = (
    "python",
    "javascript",
    "typescript",
    "react",
    "next.js",
    "node.js",
    "fastapi",
    "django",
    "postgresql",
    "sql",
    "aws",
    "azure",
    "docker",
    "kubernetes",
    "machine learning",
    "data analysis",
    "pandas",
    "tensorflow",
    "figma",
    "product strategy",
)


def _latest_resume_query(user_id: uuid.UUID):
    return (
        select(UserDocument)
        .where(
            UserDocument.user_id == user_id,
            UserDocument.doc_type == "resume",
        )
        .order_by(UserDocument.is_primary.desc(), UserDocument.embedded_at.desc().nulls_last())
        .limit(1)
    )


def _extract_skills_from_resume(resume_text: str | None) -> list[str]:
    text = (resume_text or "").lower()
    found: list[str] = []
    for skill in SKILL_HINTS:
        if skill in text and skill.title().replace("Sql", "SQL") not in found:
            found.append(skill.title().replace("Sql", "SQL").replace("Aws", "AWS"))
    return found[:10]


def _infer_years_experience(resume_text: str | None) -> int | None:
    text = (resume_text or "").lower()
    explicit = [
        int(match.group(1))
        for match in re.finditer(r"(\d{1,2})\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+)?experience", text)
    ]
    if explicit:
        return max(explicit)
    if any(word in text for word in ("fresher", "new graduate", "recent graduate", "student")):
        return 0
    date_years = [int(y) for y in re.findall(r"\b(20\d{2}|19\d{2})\b", text)]
    current_year = datetime.now(timezone.utc).year
    plausible_starts = [year for year in date_years if 1990 <= year <= current_year]
    if plausible_starts:
        oldest = min(plausible_starts)
        inferred = current_year - oldest
        if 0 <= inferred <= 60:
            return inferred
    return None


def _experience_level_from_years(years: int | None) -> str | None:
    if years is None:
        return None
    if years <= 1:
        return "fresher"
    if years <= 3:
        return "junior"
    if years <= 6:
        return "mid"
    if years <= 10:
        return "senior"
    return "lead"


def _experience_level_label(level: str | None) -> str:
    normalized = (level or "").lower()
    labels = {
        "fresher": "Fresher",
        "entry": "Entry-level",
        "entry-level": "Entry-level",
        "junior": "Junior",
        "mid": "Mid-level",
        "senior": "Senior",
        "lead": "Lead",
        "principal": "Principal",
    }
    return labels.get(normalized, "")


def _experience_prefix(level: str | None) -> str:
    normalized = (level or "").lower()
    if normalized in {"fresher", "entry", "entry-level"}:
        return "Fresher Entry-level"
    if normalized == "junior":
        return "Junior"
    if normalized in {"senior", "lead", "principal"}:
        return normalized.capitalize()
    return _experience_level_label(normalized)


def _derive_role_from_resume(resume_text: str | None) -> str:
    text = (resume_text or "").lower()
    for role in ROLE_HINTS:
        if role in text:
            return role.title().replace("Ui Ux", "UI UX")
    return ""


def _derive_roles_from_resume(resume_text: str | None, limit: int = 5) -> list[str]:
    text = (resume_text or "").lower()
    roles: list[str] = []
    for role in ROLE_HINTS:
        if role in text:
            label = role.title().replace("Ui Ux", "UI UX")
            if label not in roles:
                roles.append(label)
    skills = set(_extract_skills_from_resume(resume_text))
    skill_roles = [
        ("React Developer", {"React", "Javascript", "Typescript", "Next.Js"}),
        ("Python Developer", {"Python", "Fastapi", "Django"}),
        ("Data Analyst", {"SQL", "Pandas", "Data Analysis"}),
        ("ML Engineer", {"Machine Learning", "Tensorflow"}),
        ("DevOps Engineer", {"Docker", "Kubernetes", "AWS"}),
    ]
    for label, required in skill_roles:
        if skills & required and label not in roles:
            roles.append(label)
    return roles[:limit]


def _build_search_query(
    role: str,
    experience_level: str | None,
    years_experience: int | None,
    skills: list[str] | None = None,
) -> str:
    prefix = _experience_prefix(experience_level)
    query = f"{prefix} {role}".strip() if prefix else role
    if years_experience == 0 and "fresher" not in query.lower():
        query = f"Fresher {query}"
    skill_terms = [s for s in (skills or []) if s.lower() not in query.lower()][:2]
    if skill_terms:
        query = f"{query} {' '.join(skill_terms)}"
    return query.strip()[:200]


async def _resolve_search_context(
    db: AsyncSession,
    current_user: User,
    payload: JobSearchRequest,
) -> tuple[str, str, str, dict]:
    prefs_result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = prefs_result.scalar_one_or_none()

    resume_result = await db.execute(_latest_resume_query(current_user.id))
    resume = resume_result.scalar_one_or_none()

    role_source = "custom"
    role = payload.search_query.strip()
    payload_roles = [str(r).strip() for r in (payload.target_roles or []) if str(r).strip()]
    if not role and payload_roles:
        role = payload_roles[0]
        role_source = "manual.target_roles"
    if not role and prefs and prefs.target_roles:
        role = str(prefs.target_roles[0]).strip()
        role_source = "preferences.target_roles"
    if not role and prefs and prefs.current_title:
        role = prefs.current_title.strip()
        role_source = "preferences.current_title"
    if not role and current_user.headline:
        role = current_user.headline.strip()
        role_source = "profile.headline"
    if not role:
        role = _derive_role_from_resume(resume.raw_text if resume else None)
        role_source = "resume"
    if not role:
        role = "Software Engineer"
        role_source = "default"

    skills = _extract_skills_from_resume(resume.raw_text if resume else None)
    inferred_years = _infer_years_experience(resume.raw_text if resume else None)
    years_experience = (
        payload.years_experience
        if payload.years_experience is not None
        else prefs.years_experience if prefs and prefs.years_experience is not None
        else inferred_years
    )
    experience_level = (
        payload.experience_level
        or (prefs.experience_level if prefs else None)
        or _experience_level_from_years(years_experience)
    )
    search_query = _build_search_query(role, experience_level, years_experience, skills)

    requested_location = payload.location.strip()
    location = requested_location or "Remote"
    work_modes = _split_pref_values(payload.work_mode)
    preferred_locations = [str(loc).strip() for loc in (payload.preferred_locations or []) if str(loc).strip()]
    if prefs or preferred_locations:
        if not preferred_locations and prefs:
            preferred_locations = [str(loc).strip() for loc in (prefs.preferred_locations or []) if str(loc).strip()]
        if not work_modes and prefs:
            work_modes = _split_pref_values(prefs.work_mode)
        primary_work_mode = work_modes[0] if work_modes else ""
        if primary_work_mode == "remote":
            location = "Remote"
        elif primary_work_mode in {"hybrid", "onsite"} and requested_location in {"", "Any", "Remote"} and preferred_locations:
            location = preferred_locations[0]
    work_mode = ",".join(work_modes)

    source = {
        "role_source": role_source,
        "location_source": "preferences" if prefs and location != requested_location else "custom",
        "work_mode": work_mode or None,
        "experience_level": experience_level,
        "years_experience": years_experience,
        "job_type": payload.job_type or (prefs.job_type if prefs else None),
        "resume_skills": skills,
        "preference_id": str(prefs.id) if prefs else None,
        "resume_id": str(resume.id) if resume else None,
    }
    return search_query[:200], location[:200], work_mode, source


@router.get("/search/profile", response_model=JobSearchProfileResponse)
async def get_job_search_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prefs_result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = prefs_result.scalar_one_or_none()
    resume_result = await db.execute(_latest_resume_query(current_user.id))
    resume = resume_result.scalar_one_or_none()
    resume_text = resume.raw_text if resume else None

    resume_roles = _derive_roles_from_resume(resume_text)
    skills = _extract_skills_from_resume(resume_text)
    inferred_years = _infer_years_experience(resume_text)
    saved_years = prefs.years_experience if prefs and prefs.years_experience is not None else None
    years = saved_years if saved_years is not None else inferred_years
    level = (prefs.experience_level if prefs else None) or _experience_level_from_years(years)

    saved_roles = [str(role).strip() for role in (prefs.target_roles or []) if str(role).strip()] if prefs else []
    role = (
        saved_roles[0]
        if saved_roles
        else (prefs.current_title.strip() if prefs and prefs.current_title else "")
        or (resume_roles[0] if resume_roles else "")
        or "Software Engineer"
    )

    work_mode = (prefs.work_mode if prefs else None) or "remote"
    work_modes = _split_pref_values(work_mode)
    primary_work_mode = work_modes[0] if work_modes else "remote"
    locations = [str(loc).strip() for loc in (prefs.preferred_locations or []) if str(loc).strip()] if prefs else []
    location = "Remote" if primary_work_mode == "remote" else (locations[0] if locations else "Any")

    missing_fields: list[str] = []
    if not resume:
        missing_fields.append("resume")
    if not saved_roles and not (prefs and prefs.current_title) and not resume_roles:
        missing_fields.append("target role")
    if years is None:
        missing_fields.append("years of experience")
    if any(mode in {"hybrid", "onsite"} for mode in work_modes) and not locations:
        missing_fields.append("preferred city")
    if not prefs or not _split_pref_values(prefs.job_type):
        missing_fields.append("job type")

    notes: list[str] = []
    if resume_roles:
        notes.append(f"Resume suggests: {', '.join(resume_roles[:3])}.")
    if skills:
        notes.append(f"Top skills found: {', '.join(skills[:5])}.")
    if inferred_years is not None and saved_years is None:
        notes.append(f"Inferred {inferred_years} year(s) from resume; confirm if wrong.")
    elif saved_years is not None:
        notes.append(f"Using saved {saved_years} year(s) experience.")

    saved_preferences = {
        "current_title": prefs.current_title if prefs else None,
        "experience_level": prefs.experience_level if prefs else None,
        "years_experience": prefs.years_experience if prefs else None,
        "job_type": prefs.job_type if prefs else None,
        "work_mode": prefs.work_mode if prefs else None,
        "target_roles": prefs.target_roles or [] if prefs else [],
        "preferred_locations": prefs.preferred_locations or [] if prefs else [],
        "salary_min": prefs.salary_min if prefs else None,
        "salary_max": prefs.salary_max if prefs else None,
        "bio": prefs.bio if prefs else None,
    }

    return JobSearchProfileResponse(
        resume_found=resume is not None,
        resume_id=resume.id if resume else None,
        resume_filename=resume.filename if resume else None,
        role_suggestions=list(
            dict.fromkeys(
                saved_roles
                + ([prefs.current_title.strip()] if prefs and prefs.current_title else [])
                + resume_roles
            )
        )[:6],
        skills=skills,
        inferred_years_experience=inferred_years,
        inferred_experience_level=level,
        saved_preferences=saved_preferences,
        search_query_preview=_build_search_query(role, level, years, skills),
        location_preview=location,
        work_mode_preview=work_mode,
        missing_fields=missing_fields,
        analysis_notes=notes,
    )


# ---------------------------------------------------------------------------
# Strategy preview endpoints — show the user what the system WOULD search.
#
# These don't actually fire searches. They surface the catalogs from
# ``app.services.search_presets`` so the UI can display the query plan
# (Google dorks, company career pages, ready-to-fetch job-board URLs)
# before the user clicks "Run search".
# ---------------------------------------------------------------------------


@router.get("/search/dorks")
async def list_search_dorks(
    q: str = "GenAI Python fresher",
    location: str = "India",
    region: str = "india",
    limit: int = 10,
    current_user: User = Depends(get_current_user),
):
    """Return Google dork strings the system would fire for a query.

    Region defaults to ``"india"`` (filters to India-targeted dorks).
    Pass ``region="global"`` for the full 17-dork list.
    """
    from app.services.search_presets import GOOGLE_DORKS, dorks_for_engine

    if region.lower() == "global":
        dorks = list(GOOGLE_DORKS)
    else:
        # All current dorks are google_cse-tagged, but include any
        # engine so future additions to non-Google dorks also flow through.
        dorks = list(GOOGLE_DORKS)

    out: list[dict] = []
    for d in dorks[: max(1, min(limit, 50))]:
        raw_dork = d.get("dork", "")
        # Substitute {q} / {loc} / {location} placeholders if present.
        for needle, repl in (
            ("{q}", q),
            ("{loc}", location),
            ("{location}", location),
        ):
            raw_dork = raw_dork.replace(needle, repl)
        out.append({
            "name": d.get("name", ""),
            "dork": raw_dork,
            "use_for": d.get("use_for", ""),
            "engine": d.get("engine", "google_cse"),
            "url": f"https://www.google.com/search?q={urllib.parse.quote_plus(raw_dork)}",
        })
    return {"q": q, "location": location, "region": region, "count": len(out), "dorks": out}


@router.get("/search/companies")
async def list_company_careers(
    region: str = "all",
    current_user: User = Depends(get_current_user),
):
    """Return the 16 company career pages the system can scrape directly."""
    from app.services.search_presets import COMPANY_CAREER_PAGES

    pages = list(COMPANY_CAREER_PAGES)
    indian_keywords = (
        "tcs", "infosys", "wipro", "hcl", "tech mahindra", "cognizant",
        "capgemini", "accenture", "ltimindtree", "mindtree", "mphasis",
    )
    if region.lower() == "india":
        pages = [
            c for c in pages
            if any(kw in c.get("name", "").lower() for kw in indian_keywords)
        ] or pages
    elif region.lower() == "global":
        pages = [
            c for c in pages
            if not any(kw in c.get("name", "").lower() for kw in indian_keywords)
        ]

    out: list[dict] = []
    for c in pages:
        out.append({
            "name": c.get("name", ""),
            "url": c.get("url", ""),
            "apply_via": c.get("apply_via", "browser_use"),
            "notes": c.get("notes", ""),
        })
    return {"region": region, "count": len(out), "companies": out}


@router.get("/search/presets")
async def list_search_presets(
    q: str = "GenAI Python fresher",
    location: str = "India",
    region: str = "all",
    limit: int = 25,
    current_user: User = Depends(get_current_user),
):
    """Return ready-to-fetch job-board URLs for a query.

    These are the 27 SEARCH_PRESETS from ``search_presets.py`` with
    ``{q}`` and ``{loc}`` substituted.  Some presets have fully-baked
    URLs (e.g. Naukri's direct search) — those pass through unchanged.
    """
    from app.services.search_presets import SEARCH_PRESETS, build_url, presets_for_region

    if region.lower() in ("india", "global", "remote"):
        presets = presets_for_region(region)
    else:
        presets = list(SEARCH_PRESETS)

    out: list[dict] = []
    for preset in presets[: max(1, min(limit, 50))]:
        try:
            url = build_url(preset, q=q, loc=location, location=location)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to build URL for preset %s: %s", preset.get("name", "?"), exc
            )
            url = preset.get("url", "")
        out.append({
            "name": preset.get("name", ""),
            "url": url,
            "method": preset.get("method", "fetch"),
            "region": preset.get("region", "global"),
            "date_filter": preset.get("date_filter", ""),
            "exp_filter": preset.get("exp_filter", ""),
            "notes": preset.get("notes", ""),
        })
    return {"q": q, "location": location, "region": region, "count": len(out), "presets": out}


@router.post("/search/natural")
@limiter.limit("10/minute")
async def natural_language_search(
    request: Request,
    payload: NLSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept a natural language job query, extract parameters, return interpretation + results."""
    from app.agents.harness import get_harness

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="nl_job_search",
        status="running",
        input={"query": payload.query},
    )
    db.add(agent_run)
    await db.flush()

    harness = await get_harness()
    try:
        harness_result = await asyncio.wait_for(
            harness.run(
                user_id=str(current_user.id),
                task_type="nl_job_search",
                context={"query": payload.query},
                user_settings={},
                run_id=run_id,
            ),
            timeout=NL_SEARCH_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        agent_run.status = "failed"
        agent_run.output = {"error": f"Timed out after {NL_SEARCH_TIMEOUT_SECONDS}s"}
        await db.flush()
        raise HTTPException(status_code=504, detail="Natural language search timed out") from None
    apply_harness_result(agent_run, harness_result)
    await db.flush()
    return {"run_id": run_id, "status": agent_run.status}


async def _resolve_live_browser(
    db: AsyncSession,
    current_user: User,
    request_value: bool,
) -> bool:
    """Merge per-user preference with the request.

    The request flag wins when the caller explicitly opted in (True) — this
    lets a UI button force the visible browser for a one-off run.  When the
    caller didn't override (False), the user's saved ``prefer_live_browser``
    preference decides.  Defaulting at the schema layer stays False so
    BYOK-no-preference users still get the fast headless waterfall.
    """
    if request_value:
        return True
    prefs_result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = prefs_result.scalar_one_or_none()
    return bool(prefs and getattr(prefs, "prefer_live_browser", False))


@router.post("/search", response_model=JobSearchResponse)
@limiter.limit("10/minute")
async def search_jobs(
    request: Request,
    payload: JobSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.max_results > 25:
        raise HTTPException(status_code=400, detail="max_results cannot exceed 25")

    # Block the run early if the user hasn't configured an LLM model yet.
    # Otherwise the agent silently returns zero jobs (BYOK apps fail with
    # "Agent failed" + no detail). 409 signals "you must finish setup first".
    from app.models.db import UserModelSettings
    model_row = (await db.execute(
        select(UserModelSettings).where(
            UserModelSettings.user_id == current_user.id,
            UserModelSettings.is_active == True,  # noqa: E712
        )
    )).scalars().first()
    if not model_row:
        raise HTTPException(
            status_code=409,
            detail="No active model configured. Pick a provider under Settings → AI Model before running job search.",
        )

    search_query, location, work_mode, search_source = await _resolve_search_context(db, current_user, payload)
    live_browser = await _resolve_live_browser(db, current_user, payload.live_browser)

    titles = [t.strip() for t in (payload.titles or []) if t.strip()]
    structured_locations = [loc.strip() for loc in (payload.locations or []) if loc.strip()]
    if titles:
        search_query = " ".join(titles)
    if structured_locations:
        location = structured_locations[0]
    platforms = payload.platforms or ["linkedin", "indeed", "naukri"]

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="job_search",
        status="running",
        input={
            "search_query": search_query,
            "location": location,
            "max_results": payload.max_results,
            "live_browser": live_browser,
            "work_mode": work_mode,
            "search_source": search_source,
            "titles": titles,
            "platforms": platforms,
        },
    )
    db.add(agent_run)
    await db.flush()

    from app.services.queue_service import make_job_search_id

    remote = (payload.remote or "").strip() or work_mode or "any"

    try:
        queue_job_id, queued = await enqueue_job_search(
            user_id=str(current_user.id),
            run_id=run_id,
            search_query=search_query,
            location=location,
            max_results=payload.max_results,
            live_browser=live_browser,
            work_mode=work_mode,
            job_id=make_job_search_id(
                str(current_user.id), search_query, location, payload.max_results
            ),
            platforms=platforms,
            remote=remote,
        )
    except RuntimeError as exc:
        logger.warning("Job search enqueue failed for run %s: %s", run_id, exc)
        raise HTTPException(status_code=503, detail="Job search service unavailable") from exc
    return JobSearchResponse(run_id=run_id, queue_job_id=queue_job_id, queued=queued)

@router.get("/applications", response_model=list[ApplicationResponse])
async def list_applications(
    status: str | None = None,
    location: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if status and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"status must be one of: {VALID_STATUSES}"
        )

    query = select(JobApplication).where(JobApplication.user_id == current_user.id)
    if status:
        query = query.where(JobApplication.status == status)
    result = await db.execute(
        query.order_by(JobApplication.applied_at.desc().nulls_last())
    )
    return [
        app
        for app in result.scalars().all()
        if not is_example_job_url(app.job_url)
        and _matches_location_filter(app, location)
    ]


@router.patch("/applications/{application_id}/status", response_model=ApplicationResponse)
async def update_application_status(
    application_id: uuid.UUID,
    body: StatusUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"status must be one of: {VALID_STATUSES}"
        )

    result = await db.execute(
        select(JobApplication).where(
            JobApplication.id == application_id,
            JobApplication.user_id == current_user.id,
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app.status = body.status
    if body.status == "applied" and not app.applied_at:
        app.applied_at = datetime.now(timezone.utc)
    return app


@router.post("/applications/{application_id}/prepare-apply")
@limiter.limit("5/hour")
async def prepare_application_apply(
    application_id: uuid.UUID,
    body: PrepareApplyBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(JobApplication).where(
            JobApplication.id == application_id,
            JobApplication.user_id == current_user.id,
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if not app.job_url:
        raise HTTPException(status_code=400, detail="Application has no job URL")

    live_browser = await _resolve_live_browser(db, current_user, body.live_browser)

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="apply_prepare",
        status="running",
        input={"application_id": str(application_id), "live_browser": live_browser},
    )
    db.add(agent_run)
    await db.commit()

    async def _run() -> None:
        from app.core.database import AsyncSessionLocal
        from app.core.event_bus import emit
        from app.core.model_router import _build_llm
        from app.core.sync_db import fetch_model_settings
        from app.services.browser_control_service import run_browser_task_with_captcha_retry as run_browser_task
        from app.services.form_filler_service import build_user_form_profile, _build_profile_context

        try:
            model_settings = fetch_model_settings(str(current_user.id))
            if not model_settings:
                raise RuntimeError("No active model settings configured")
            llm = _build_llm(model_settings)
            profile = build_user_form_profile(str(current_user.id))
            profile_context = _build_profile_context(profile, app.jd_text or "")
            task = (
                "Prepare this job application in the visible browser.\n\n"
                f"JOB URL: {app.job_url}\n"
                f"TARGET ROLE: {app.role} at {app.company}\n\n"
                f"{profile_context}\n\n"
                "Steps:\n"
                "1. Open the job URL.\n"
                "2. Click Apply / Apply Now if present.\n"
                "3. Fill required fields using exact profile data above.\n"
                "4. For open-ended questions, answer from resume/background and job description.\n"
                "5. If multiple pages exist, continue until final review page.\n"
                "6. Stop before final Submit / Send Application. Do not submit.\n"
                "7. If CAPTCHA, OTP, payment, account creation, or unknown required data appears, stop and report REQUIRES_MANUAL."
            )
            result_text = await run_browser_task(
                llm=llm,
                task=task,
                user_id=str(current_user.id),
                max_steps=25,
                live_browser=live_browser,
                run_id=run_id,
            )
            emit(run_id, "checkpoint", {
                "type": "submit_application",
                "application_id": str(application_id),
                "company": app.company,
                "role": app.role,
                "job_url": app.job_url,
                "message": "Review browser page. Submit manually only if everything looks correct.",
                "browser_result": result_text[:1000],
            })
            async with AsyncSessionLocal() as fresh_db:
                res = await fresh_db.execute(select(AgentRun).where(AgentRun.id == uuid.UUID(run_id)))
                run = res.scalar_one_or_none()
                if run:
                    run.status = "awaiting_approval"
                    run.output = {"type": "submit_application", "application_id": str(application_id)}
                    await fresh_db.commit()
        except Exception as exc:
            logger.warning("Application preparation fallback for run %s: %s", run_id, exc)
            fallback = {
                "type": "submit_application",
                "application_id": str(application_id),
                "company": app.company,
                "role": app.role,
                "job_url": app.job_url,
                "message": (
                    "Browser automation could not finish. Open the job URL, review the page, "
                    "and submit manually only if everything looks correct."
                ),
                "browser_result": "Automation fallback: browser preparation failed",
            }
            emit(run_id, "checkpoint", fallback)
            async with AsyncSessionLocal() as fresh_db:
                res = await fresh_db.execute(select(AgentRun).where(AgentRun.id == uuid.UUID(run_id)))
                run = res.scalar_one_or_none()
                if run:
                    run.status = "awaiting_approval"
                    run.output = fallback
                    await fresh_db.commit()

    import asyncio
    asyncio.create_task(_run())
    return {"run_id": run_id, "status": "running"}
