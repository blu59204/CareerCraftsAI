from __future__ import annotations

from pydantic import BaseModel, Field


class JobSearchQuerySchema(BaseModel):
    """Structured job-search request (preferred over free-text query).

    Used by POST /jobs/search when the caller supplies parsed titles
    (e.g. from nl_search). Missing fields fall back to legacy resolution
    from preferences/resume in the endpoint.
    """

    titles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=lambda: ["linkedin", "indeed", "naukri"])
    remote: str = "any"
    # Accepted for forward-compat; sources currently use fixed windows
    # (e.g. JobSpy hours_old=72). Wired per-source when providers support it.
    posted_within_days: int = Field(default=14, ge=1, le=90)
