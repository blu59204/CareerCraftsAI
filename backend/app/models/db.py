import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String)
    avatar_url: Mapped[str | None] = mapped_column(String)
    google_id: Mapped[str | None] = mapped_column(String, unique=True)
    supabase_uid: Mapped[str | None] = mapped_column(String, unique=True)
    phone: Mapped[str | None] = mapped_column(String)
    linkedin_url: Mapped[str | None] = mapped_column(String)
    headline: Mapped[str | None] = mapped_column(String)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    linkedin_email_enc: Mapped[str | None] = mapped_column(Text)
    linkedin_password_enc: Mapped[str | None] = mapped_column(Text)
    auto_mode: Mapped[str] = mapped_column(String, default="drafts")  # 'auto' or 'drafts'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    model_settings: Mapped[list["UserModelSettings"]] = relationship(back_populates="user")
    documents: Mapped[list["UserDocument"]] = relationship(back_populates="user")
    applications: Mapped[list["JobApplication"]] = relationship(back_populates="user")
    leads: Mapped[list["Lead"]] = relationship(back_populates="user")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="user")
    preferences: Mapped["UserPreferences | None"] = relationship(back_populates="user", uselist=False)


class UserModelSettings(Base):
    __tablename__ = "user_model_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String, nullable=False)
    api_key_enc: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String)
    ollama_url: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="model_settings")


class UserDocument(Base):
    __tablename__ = "user_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    doc_type: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    ats_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ats_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship(back_populates="documents")


class JobApplication(Base):
    __tablename__ = "job_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    company: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    job_url: Mapped[str | None] = mapped_column(String)
    jd_text: Mapped[str | None] = mapped_column(Text)
    match_score: Mapped[int | None] = mapped_column(Integer)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_documents.id"))
    cover_letter: Mapped[str | None] = mapped_column(Text)
    cover_letter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_documents.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, default="saved")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    followup_day5: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    followup_day12: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="applications")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    company: Mapped[str | None] = mapped_column(String)
    linkedin_url: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="cold")
    last_contact: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="leads")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    agent_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="running")
    input: Mapped[dict | None] = mapped_column(JSONB)
    output: Mapped[dict | None] = mapped_column(JSONB)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="agent_runs")


class CoverLetterVersion(Base):
    __tablename__ = "cover_letter_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_applications.id", ondelete="CASCADE")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_documents.id"))
    tone: Mapped[str] = mapped_column(String(10), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_applications.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255))
    questions: Mapped[list] = mapped_column(JSONB, default=list)
    answers: Mapped[list] = mapped_column(JSONB, default=list)
    scores: Mapped[list] = mapped_column(JSONB, default=list)
    overall_score: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SalaryReport(Base):
    __tablename__ = "salary_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_applications.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    p25: Mapped[int] = mapped_column(Integer, nullable=False)
    p50: Mapped[int] = mapped_column(Integer, nullable=False)
    p75: Mapped[int] = mapped_column(Integer, nullable=False)
    offer_amount: Mapped[int | None] = mapped_column(Integer)
    classification: Mapped[str | None] = mapped_column(String(20))
    negotiation_script: Mapped[dict | None] = mapped_column(JSONB)
    data_sources: Mapped[list] = mapped_column(JSONB, default=list)
    data_unavailable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompanyIntelModel(Base):
    __tablename__ = "company_intel"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    overview: Mapped[str | None] = mapped_column(Text)
    culture_summary: Mapped[str | None] = mapped_column(Text)
    news_items: Mapped[list] = mapped_column(JSONB, default=list)
    tech_stack: Mapped[list] = mapped_column(JSONB, default=list)
    glassdoor_sentiment: Mapped[str | None] = mapped_column(String(10))
    partial_data: Mapped[dict | None] = mapped_column(JSONB)
    researched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResumePersona(Base):
    __tablename__ = "resume_personas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    primary_resume_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_documents.id", ondelete="SET NULL"), nullable=True
    )
    target_keywords: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LinkedInOutreachQueue(Base):
    __tablename__ = "linkedin_outreach_queue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_title: Mapped[str | None] = mapped_column(String(255))
    contact_linkedin_url: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending_approval")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AtsScore(Base):
    __tablename__ = "ats_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_documents.id", ondelete="SET NULL"), nullable=True
    )
    job_application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_applications.id"), nullable=True
    )
    composite_score: Mapped[int] = mapped_column(Integer, nullable=False)
    keyword_score: Mapped[int] = mapped_column(Integer, nullable=False)
    readability_score: Mapped[int] = mapped_column(Integer, nullable=False)
    format_score: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_keywords: Mapped[list] = mapped_column(JSONB, default=list)
    suggestions: Mapped[list] = mapped_column(JSONB, default=list)
    flesch_kincaid: Mapped[float | None] = mapped_column(nullable=True)
    avg_sentence_length: Mapped[float | None] = mapped_column(nullable=True)
    format_checks: Mapped[dict] = mapped_column(JSONB, default=dict)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    experience_level: Mapped[str | None] = mapped_column(String)
    job_type: Mapped[str | None] = mapped_column(String)
    work_mode: Mapped[str | None] = mapped_column(String)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    target_roles: Mapped[list | None] = mapped_column(JSONB, default=list)
    preferred_locations: Mapped[list | None] = mapped_column(JSONB, default=list)
    current_title: Mapped[str | None] = mapped_column(String)
    bio: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="preferences")
