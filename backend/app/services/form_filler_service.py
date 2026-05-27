"""
form_filler_service.py — LLM-powered job application form filling.

Uses the LLM to dynamically generate answers for any form field based on:
1. User profile from DB (name, email, phone, experience, preferences)
2. User's resume text from RAG
3. Agent memory (past applications, preferences, learnings)
4. Job description context

The LLM sees the form field label and generates the best answer using all
available user context. This handles ANY form — Workday, Greenhouse, Lever,
custom ATS, or company career pages.
"""
import logging
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.sync_db import _get_sync_factory, fetch_user_profile_text
from app.services.browser_control_service import run_browser_task

logger = logging.getLogger(__name__)


@dataclass
class UserFormProfile:
    """All data needed to fill any job application form."""
    full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    current_title: str = ""
    experience_level: str = ""
    experience_years: str = ""
    work_mode: str = ""
    salary_min: int | None = None
    salary_max: int | None = None
    preferred_locations: list[str] = field(default_factory=list)
    target_roles: list[str] = field(default_factory=list)
    bio: str = ""
    resume_text: str = ""
    skills: str = ""
    education: str = ""
    memory_context: str = ""


def build_user_form_profile(user_id: str) -> UserFormProfile:
    """Fetch all user data from DB + memory for form filling."""
    from sqlalchemy import select
    from app.models.db import User, UserPreferences

    factory = _get_sync_factory()
    with factory() as db:
        user = db.execute(select(User).where(User.supabase_uid == user_id)).scalars().first()
        prefs = db.execute(
            select(UserPreferences).where(UserPreferences.user_id == user.id)
        ).scalars().first() if user else None

    resume_text = fetch_user_profile_text(user_id)
    full_name = user.full_name or "" if user else ""
    parts = full_name.split() if full_name else []

    # Map experience level to years
    exp_years_map = {"entry": "0-2", "junior": "1-3", "mid": "3-5", "senior": "5-10", "lead": "8-12", "principal": "10+"}
    exp_level = prefs.experience_level or "mid" if prefs else "mid"

    return UserFormProfile(
        full_name=full_name,
        first_name=parts[0] if parts else "",
        last_name=" ".join(parts[1:]) if len(parts) > 1 else "",
        email=user.email or "" if user else "",
        phone=user.phone or "" if user else "",
        linkedin_url=user.linkedin_url or "" if user else "",
        current_title=prefs.current_title or "" if prefs else "",
        experience_level=exp_level,
        experience_years=exp_years_map.get(exp_level, "3-5"),
        work_mode=prefs.work_mode or "remote" if prefs else "remote",
        salary_min=prefs.salary_min if prefs else None,
        salary_max=prefs.salary_max if prefs else None,
        preferred_locations=prefs.preferred_locations or [] if prefs else [],
        target_roles=prefs.target_roles or [] if prefs else [],
        bio=prefs.bio or "" if prefs else "",
        resume_text=resume_text,
    )


def _build_profile_context(profile: UserFormProfile, job_description: str = "") -> str:
    """Build the full context string the LLM uses to answer form questions."""
    salary = ""
    if profile.salary_min and profile.salary_max:
        salary = f"{profile.salary_min} - {profile.salary_max} per annum"
    elif profile.salary_min:
        salary = f"{profile.salary_min}+ per annum"

    return f"""USER PROFILE (use this to fill form fields):

Name: {profile.full_name}
First Name: {profile.first_name}
Last Name: {profile.last_name}
Email: {profile.email}
Phone: {profile.phone}
LinkedIn: {profile.linkedin_url}
Current Title: {profile.current_title}
Experience: {profile.experience_years} years ({profile.experience_level} level)
Work Preference: {profile.work_mode}
Salary Expectation: {salary or 'Negotiable'}
Preferred Locations: {', '.join(profile.preferred_locations) or 'Flexible'}
Target Roles: {', '.join(profile.target_roles) or profile.current_title}

RESUME/BACKGROUND:
{profile.resume_text[:1500]}

BIO:
{profile.bio[:500] if profile.bio else 'See resume above'}

JOB DESCRIPTION:
{job_description[:1000] if job_description else 'Not provided'}"""


FORM_FILLER_SYSTEM = """You are an expert job application form filler. You have access to the \
candidate's complete profile and must fill every form field accurately.

RULES:
- Use EXACT data from the profile for factual fields (name, email, phone, etc.)
- For open-ended questions ("Why this role?", "Tell us about yourself"), write compelling \
  2-3 sentence answers using the resume and job description context.
- For dropdowns/selects, pick the closest matching option.
- For yes/no questions about work authorization: answer "Yes" for authorized, "No" for sponsorship needed.
- For "How did you hear about us?": say "LinkedIn" or "Job Board".
- For salary: use the salary expectation from profile. If field is optional and no data, skip.
- NEVER fabricate credentials, degrees, or certifications not in the resume.
- NEVER leave required fields empty.
- For ambiguous fields, use the safest reasonable default."""


def generate_form_answers(
    llm: BaseChatModel,
    profile: UserFormProfile,
    form_fields: list[str],
    job_description: str = "",
) -> dict[str, str]:
    """Use LLM to generate answers for a list of form field labels.

    Args:
        llm: LLM instance
        profile: User's complete form profile
        form_fields: List of field labels/questions from the form
        job_description: JD for context

    Returns:
        Dict mapping field label → answer
    """
    context = _build_profile_context(profile, job_description)
    fields_text = "\n".join(f"- {f}" for f in form_fields)

    response = llm.invoke([
        SystemMessage(content=FORM_FILLER_SYSTEM),
        HumanMessage(content=f"""{context}

FORM FIELDS TO FILL:
{fields_text}

For each field, provide the answer. Format:
FIELD: <field label>
ANSWER: <your answer>

Fill ALL fields listed above."""),
    ])

    # Parse response into dict
    answers = {}
    current_field = None
    for line in response.content.strip().split("\n"):
        if line.startswith("FIELD:"):
            current_field = line.replace("FIELD:", "").strip()
        elif line.startswith("ANSWER:") and current_field:
            answers[current_field] = line.replace("ANSWER:", "").strip()
            current_field = None

    return answers


async def fill_and_submit_form(
    llm: BaseChatModel,
    user_id: str,
    job_url: str,
    resume_path: str | None = None,
    cover_letter: str = "",
    job_description: str = "",
) -> dict:
    """Navigate to a job URL, use LLM to fill the form with user data, and submit.

    The browser-use agent is given the user's full profile context so the LLM
    can generate appropriate answers for ANY form field it encounters.

    Args:
        llm: LLM for browser agent + form answer generation
        user_id: User ID for persistent browser session
        job_url: URL of the job posting or application form
        resume_path: Path to tailored resume PDF to upload
        cover_letter: Pre-generated cover letter text
        job_description: JD text for context

    Returns:
        Dict with status and message
    """
    profile = build_user_form_profile(user_id)
    context = _build_profile_context(profile, job_description)

    # Build the browser-use task with full user context so LLM can answer any field
    task = f"""You are filling a job application form. You have the candidate's complete profile below.
Use this data to fill EVERY field on the form accurately.

{context}

COVER LETTER (use if there's a cover letter field):
{cover_letter[:1000] if cover_letter else 'Write 2-3 compelling sentences about why this candidate fits the role, based on the resume and JD above.'}

TASK:
1. Go to {job_url}
2. Click "Apply" / "Apply Now" / "Submit Application" (whatever the apply button says)
3. For EVERY form field you see:
   - Text inputs: type the correct value from the profile above
   - Dropdowns: select the closest matching option
   - Radio buttons: select the appropriate option
   - Checkboxes: check if applicable
   - File upload: {'upload resume from ' + resume_path if resume_path else 'skip or use pre-uploaded'}
   - Text areas (cover letter, "why this role?"): use the cover letter above or write a compelling answer
4. If the form has multiple pages, fill each page completely then click Next/Continue
5. On the final page, click Submit
6. Confirm submission was successful

IMPORTANT:
- Fill fields using EXACT profile data (don't make up info)
- For "First Name" use: {profile.first_name}
- For "Last Name" use: {profile.last_name}
- For "Email" use: {profile.email}
- For "Phone" use: {profile.phone}
- For experience/years: {profile.experience_years} years
- For salary: {profile.salary_min or 'negotiable'}
- If you encounter CAPTCHA/OTP/video, stop and report 'REQUIRES_MANUAL'
- If account creation is needed, use email {profile.email} with password 'TempPass123!'"""

    try:
        result = await run_browser_task(llm, task, user_id, max_steps=30)
        if "REQUIRES_MANUAL" in (result or ""):
            return {"status": "requires_manual", "message": result}
        return {"status": "applied", "message": result or "Form submitted successfully"}
    except Exception as exc:
        logger.error("Form filling failed for %s: %s", job_url, exc)
        return {"status": "failed", "message": str(exc)}
