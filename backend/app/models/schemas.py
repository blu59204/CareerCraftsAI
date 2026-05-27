import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str | None = None
    supabase_uid: str = Field(min_length=36, max_length=36)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    avatar_url: str | None
    headline: str | None
    phone: str | None
    linkedin_url: str | None
    onboarding_completed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=200)
    headline: str | None = Field(None, max_length=300)
    phone: str | None = Field(None, max_length=30)
    linkedin_url: str | None = Field(None, max_length=500)
    onboarding_completed: bool | None = None


class UserPreferencesSchema(BaseModel):
    experience_level: str | None = None
    job_type: str | None = None
    work_mode: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    target_roles: list[str] = []
    preferred_locations: list[str] = []
    current_title: str | None = Field(None, max_length=200)
    bio: str | None = Field(None, max_length=2000)


class UserPreferencesResponse(UserPreferencesSchema):
    id: uuid.UUID
    user_id: uuid.UUID

    model_config = {"from_attributes": True}


class ModelSettingsCreate(BaseModel):
    provider: Literal["anthropic", "openai", "google", "ollama", "nvidia_nim"]
    api_key: str = Field(min_length=1, max_length=200)
    model_name: str
    ollama_url: str | None = None


class ModelSettingsResponse(BaseModel):
    id: uuid.UUID
    provider: str
    model_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}


# ─── Cover Letter Schemas ─────────────────────────────────────────────────────


class CoverLetterRequest(BaseModel):
    job_application_id: uuid.UUID
    tone: Literal["formal", "casual", "bold"] = "formal"


class CoverLetterResponse(BaseModel):
    id: uuid.UUID
    content: str
    tone: str
    version_number: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Interview Coach Schemas ──────────────────────────────────────────────────


class InterviewStartRequest(BaseModel):
    role: str
    company: str | None = None
    job_application_id: uuid.UUID | None = None
    question_type: Literal["behavioral", "technical", "situational"] | None = None


class AnswerSubmitRequest(BaseModel):
    answer_text: str = Field(min_length=10)


class AnswerEvaluation(BaseModel):
    score: int = Field(ge=0, le=100)
    rating: Literal["poor", "fair", "good", "excellent"]
    tips: list[str] = Field(min_length=1)


# ─── Salary Intelligence Schemas ─────────────────────────────────────────────


class SalaryReportRequest(BaseModel):
    role: str
    company: str | None = None
    location: str
    offer_amount: int | None = None
    job_application_id: uuid.UUID | None = None


class SalaryReportResponse(BaseModel):
    id: uuid.UUID
    p25: int
    p50: int
    p75: int
    classification: str | None = None
    negotiation_script: dict | None = None
    data_unavailable: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Company Research Schemas ─────────────────────────────────────────────────


class CompanyResearchRequest(BaseModel):
    company_name: str
    force_refresh: bool = False


class CompanyIntelResponse(BaseModel):
    id: uuid.UUID
    company_name: str
    overview: str | None = None
    culture_summary: str | None = None
    news_items: list[dict] = []
    tech_stack: list[str] = []
    glassdoor_sentiment: str | None = None
    partial_data: dict | None = None
    researched_at: datetime

    model_config = {"from_attributes": True}


# ─── NL Job Search Schemas ────────────────────────────────────────────────────


class NLSearchRequest(BaseModel):
    query: str = Field(min_length=5, max_length=500)


class SearchInterpretation(BaseModel):
    role_title: str | None = None
    seniority: str | None = None
    location: str | None = None
    remote_preference: str | None = None
    salary_range: tuple[int, int] | None = None
    tech_stack: list[str] = []


# ─── Resume Persona Schemas ──────────────────────────────────────────────────


class PersonaCreate(BaseModel):
    name: str = Field(max_length=100)
    description: str | None = None
    primary_resume_id: uuid.UUID | None = None
    target_keywords: list[str] = Field(default_factory=list, max_length=50)


class PersonaUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = None
    primary_resume_id: uuid.UUID | None = None
    target_keywords: list[str] | None = None


class PersonaResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    primary_resume_id: uuid.UUID | None = None
    target_keywords: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── ATS Score Schemas ────────────────────────────────────────────────────────


class ATSScoreRequest(BaseModel):
    resume_text: str = Field(min_length=100)
    jd_text: str = Field(min_length=100)
    resume_id: uuid.UUID | None = None
    job_application_id: uuid.UUID | None = None


class ATSScoreResponse(BaseModel):
    id: uuid.UUID
    composite_score: int
    keyword_score: int
    readability_score: int
    format_score: int
    missing_keywords: list[str] = []
    suggestions: list[str] = []
    flesch_kincaid: float | None = None
    avg_sentence_length: float | None = None
    format_checks: dict = {}
    scored_at: datetime

    model_config = {"from_attributes": True}


# ─── LinkedIn Outreach Schemas ────────────────────────────────────────────────


class OutreachIdentifyRequest(BaseModel):
    company: str
    role_context: str | None = None


class OutreachMessageResponse(BaseModel):
    id: uuid.UUID
    company: str
    contact_name: str
    contact_title: str | None = None
    contact_linkedin_url: str | None = None
    message: str
    status: str
    approved_at: datetime | None = None
    sent_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
