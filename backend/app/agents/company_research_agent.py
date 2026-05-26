"""
Company Research Agent — LangGraph node that researches target companies from
multiple sources and stores intel in pgvector for cross-agent retrieval.

Sources:
  1. Company website (Firecrawl)
  2. Recent news (Exa)
  3. Tech stack (Exa)
  4. Glassdoor sentiment (Exa)

Implements 7-day cache with graceful degradation on individual source failures.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from langchain_core.documents import Document
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AgentState
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.db import AgentRun, CompanyIntelModel
from app.services.exa_service import ExaService
from app.services.rag_service import (
    chunk_text,
    get_embedding_model,
    get_vector_store,
)

logger = logging.getLogger(__name__)

CACHE_TTL_DAYS = 7
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
FIRECRAWL_TIMEOUT = 20.0


@dataclass
class CompanyIntel:
    """Structured research data about a target company."""

    company_name: str
    overview: str = ""
    culture_summary: str = ""
    news_items: list[dict[str, Any]] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    glassdoor_sentiment: Literal["positive", "neutral", "negative"] = "neutral"
    partial_data: dict[str, str] | None = None
    researched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["researched_at"] = self.researched_at.isoformat()
        return data


# ---------------------------------------------------------------------------
# Source fetching functions (each tolerates its own failures)
# ---------------------------------------------------------------------------


async def _fetch_website(company_name: str) -> dict[str, Any]:
    """Scrape company website via Firecrawl for overview and culture info."""
    api_key = settings.FIRECRAWL_API_KEY
    if not api_key:
        logger.warning("FIRECRAWL_API_KEY not configured — skipping website source")
        raise RuntimeError("Firecrawl API key not configured")

    # Attempt to scrape a search-derived URL for the company
    search_url = f"https://www.google.com/search?q={company_name}+official+website"

    payload = {
        "url": search_url,
        "formats": ["markdown"],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=FIRECRAWL_TIMEOUT) as client:
        resp = await client.post(FIRECRAWL_SCRAPE_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    content = data.get("data", {}).get("markdown", "")
    return {"content": content[:3000], "source": "website"}


async def _fetch_news(exa: ExaService, company_name: str) -> list[dict[str, Any]]:
    """Fetch recent news articles about the company via Exa."""
    results = await exa.search_news(company_name)
    news_items = []
    for r in results[:5]:
        news_items.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("text", r.get("snippet", ""))[:300],
            "published": r.get("publishedDate", ""),
        })
    return news_items


async def _fetch_tech_stack(exa: ExaService, company_name: str) -> list[str]:
    """Fetch tech stack information via Exa search."""
    results = await exa.search_tech_stack(company_name)
    # Extract technology mentions from results
    tech_mentions: list[str] = []
    for r in results:
        text = r.get("text", r.get("snippet", ""))
        # Simple extraction — the LLM will refine this later
        if text:
            tech_mentions.append(text[:500])
    return tech_mentions


async def _fetch_glassdoor(exa: ExaService, company_name: str) -> dict[str, Any]:
    """Fetch Glassdoor sentiment via Exa search."""
    query = f"{company_name} Glassdoor reviews employee sentiment culture"
    results = await exa._search(query, num_results=3)
    snippets = [r.get("text", r.get("snippet", ""))[:300] for r in results if r]
    return {"snippets": snippets, "source": "glassdoor"}


# ---------------------------------------------------------------------------
# Source aggregation with graceful degradation
# ---------------------------------------------------------------------------


async def fetch_all_sources(
    company_name: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    """
    Fetch from all 4 sources. Returns (results_dict, failures_dict).
    Each source failure is caught individually — other sources continue.
    """
    exa = ExaService()
    results: dict[str, Any] = {}
    failures: dict[str, str] = {}

    # 1. Website (Firecrawl)
    try:
        website_data = await _fetch_website(company_name)
        results["website"] = website_data
    except Exception as exc:
        logger.warning("Company research: website fetch failed for '%s': %s", company_name, exc)
        failures["website"] = str(exc)

    # 2. News (Exa)
    try:
        news_items = await _fetch_news(exa, company_name)
        results["news"] = news_items
    except Exception as exc:
        logger.warning("Company research: news fetch failed for '%s': %s", company_name, exc)
        failures["news"] = str(exc)

    # 3. Tech stack (Exa)
    try:
        tech_stack = await _fetch_tech_stack(exa, company_name)
        results["tech_stack"] = tech_stack
    except Exception as exc:
        logger.warning("Company research: tech_stack fetch failed for '%s': %s", company_name, exc)
        failures["tech_stack"] = str(exc)

    # 4. Glassdoor (Exa)
    try:
        glassdoor_data = await _fetch_glassdoor(exa, company_name)
        results["glassdoor"] = glassdoor_data
    except Exception as exc:
        logger.warning("Company research: glassdoor fetch failed for '%s': %s", company_name, exc)
        failures["glassdoor"] = str(exc)

    return results, failures


def compile_intel(
    company_name: str,
    results: dict[str, Any],
    failures: dict[str, str],
) -> CompanyIntel:
    """
    Compile fetched results into a CompanyIntel dataclass.
    Gracefully handles missing sources by using defaults.
    """
    overview = ""
    if "website" in results:
        content = results["website"].get("content", "")
        overview = content[:1500] if content else ""

    news_items = results.get("news", [])

    tech_stack_raw = results.get("tech_stack", [])
    # Flatten tech stack snippets into a simple list of tech names
    tech_stack: list[str] = tech_stack_raw if isinstance(tech_stack_raw, list) else []

    # Determine Glassdoor sentiment from snippets
    glassdoor_sentiment: Literal["positive", "neutral", "negative"] = "neutral"
    if "glassdoor" in results:
        snippets = results["glassdoor"].get("snippets", [])
        combined = " ".join(snippets).lower()
        positive_signals = ["great", "excellent", "love", "amazing", "good culture", "recommend"]
        negative_signals = ["toxic", "terrible", "avoid", "worst", "poor management", "overwork"]
        pos_count = sum(1 for s in positive_signals if s in combined)
        neg_count = sum(1 for s in negative_signals if s in combined)
        if pos_count > neg_count:
            glassdoor_sentiment = "positive"
        elif neg_count > pos_count:
            glassdoor_sentiment = "negative"

    culture_summary = ""
    if "glassdoor" in results:
        snippets = results["glassdoor"].get("snippets", [])
        culture_summary = " ".join(snippets)[:800]

    partial_data = failures if failures else None

    return CompanyIntel(
        company_name=company_name,
        overview=overview,
        culture_summary=culture_summary,
        news_items=news_items,
        tech_stack=tech_stack,
        glassdoor_sentiment=glassdoor_sentiment,
        partial_data=partial_data,
        researched_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Cache check
# ---------------------------------------------------------------------------


async def get_cached_intel(
    db: AsyncSession, user_id: str, company_name: str
) -> CompanyIntelModel | None:
    """Return cached CompanyIntel if it exists and is fresh (< 7 days)."""
    result = await db.execute(
        select(CompanyIntelModel).where(
            CompanyIntelModel.user_id == user_id,
            CompanyIntelModel.company_name == company_name,
        )
    )
    record = result.scalars().first()
    if not record:
        return None

    age_days = (datetime.now(timezone.utc) - record.researched_at.replace(tzinfo=timezone.utc)).days
    if age_days < CACHE_TTL_DAYS:
        return record
    return None


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


async def embed_company_intel(
    user_id: str, intel: CompanyIntel, model_settings: Any
) -> int:
    """Chunk and embed company intel into {user_id}_company pgvector collection."""
    # Build a text representation for embedding
    text_parts = [
        f"Company: {intel.company_name}",
        f"Overview: {intel.overview}" if intel.overview else "",
        f"Culture: {intel.culture_summary}" if intel.culture_summary else "",
        f"Tech Stack: {', '.join(intel.tech_stack)}" if intel.tech_stack else "",
        f"Glassdoor Sentiment: {intel.glassdoor_sentiment}",
    ]

    if intel.news_items:
        news_text = "\n".join(
            f"- {item.get('title', '')}: {item.get('snippet', '')}"
            for item in intel.news_items[:5]
        )
        text_parts.append(f"Recent News:\n{news_text}")

    full_text = "\n\n".join(part for part in text_parts if part)
    chunks = chunk_text(full_text)

    embeddings = get_embedding_model(model_settings)
    docs = [
        Document(
            page_content=chunk,
            metadata={
                "company_name": intel.company_name,
                "source": "company_research",
                "chunk_index": i,
            },
        )
        for i, chunk in enumerate(chunks)
    ]

    store = get_vector_store(user_id, "company", embeddings, provider=model_settings.provider)
    store.add_documents(docs)
    return len(docs)


async def save_intel_to_db(
    db: AsyncSession, user_id: str, intel: CompanyIntel
) -> CompanyIntelModel:
    """Persist or update structured JSON in company_intel table."""
    # Check if existing record for this user+company
    result = await db.execute(
        select(CompanyIntelModel).where(
            CompanyIntelModel.user_id == user_id,
            CompanyIntelModel.company_name == intel.company_name,
        )
    )
    existing = result.scalars().first()

    if existing:
        existing.overview = intel.overview
        existing.culture_summary = intel.culture_summary
        existing.news_items = intel.news_items
        existing.tech_stack = intel.tech_stack
        existing.glassdoor_sentiment = intel.glassdoor_sentiment
        existing.partial_data = intel.partial_data
        existing.researched_at = intel.researched_at
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        record = CompanyIntelModel(
            id=uuid.uuid4(),
            user_id=user_id,
            company_name=intel.company_name,
            overview=intel.overview,
            culture_summary=intel.culture_summary,
            news_items=intel.news_items,
            tech_stack=intel.tech_stack,
            glassdoor_sentiment=intel.glassdoor_sentiment,
            partial_data=intel.partial_data,
            researched_at=intel.researched_at,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record


async def log_agent_run(
    db: AsyncSession,
    user_id: str,
    status: str,
    input_data: dict[str, Any],
    output_data: dict[str, Any] | None,
    duration_ms: int,
    tokens_used: int | None = None,
) -> None:
    """Log this agent run to the agent_runs table."""
    run = AgentRun(
        id=uuid.uuid4(),
        user_id=user_id,
        agent_type="company_research",
        status=status,
        input=input_data,
        output=output_data,
        tokens_used=tokens_used,
        duration_ms=duration_ms,
    )
    db.add(run)
    await db.commit()


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------


async def company_research_node(state: AgentState) -> AgentState:
    """
    LangGraph node for company research.

    Fetches from 4 sources (website, news, tech_stack, glassdoor),
    compiles CompanyIntel with graceful degradation, caches for 7 days,
    embeds in pgvector, persists to DB, and logs the run.
    """
    user_id = state["user_id"]
    context = state["context"]
    company_name = context["company_name"]
    force_refresh = context.get("force_refresh", False)

    start_ts = time.monotonic()

    async with AsyncSessionLocal() as db:
        # --- Cache check: return cached if < 7 days old and not forced ---
        if not force_refresh:
            cached = await get_cached_intel(db, user_id, company_name)
            if cached:
                duration_ms = int((time.monotonic() - start_ts) * 1000)
                await log_agent_run(
                    db=db,
                    user_id=user_id,
                    status="completed",
                    input_data={"company_name": company_name, "cache_hit": True},
                    output_data={"company_name": cached.company_name, "cached": True},
                    duration_ms=duration_ms,
                )
                return {
                    **state,
                    "status": "completed",
                    "result": {
                        "company_name": cached.company_name,
                        "overview": cached.overview,
                        "culture_summary": cached.culture_summary,
                        "news_items": cached.news_items,
                        "tech_stack": cached.tech_stack,
                        "glassdoor_sentiment": cached.glassdoor_sentiment,
                        "partial_data": cached.partial_data,
                        "researched_at": cached.researched_at.isoformat()
                        if cached.researched_at
                        else None,
                        "cached": True,
                    },
                }

        # --- Fetch from all sources with graceful degradation ---
        results, failures = await fetch_all_sources(company_name)

        # --- Compile CompanyIntel ---
        intel = compile_intel(company_name, results, failures)

        # --- Embed in pgvector ---
        try:
            # Get model settings for embedding
            from app.models.db import UserModelSettings
            from sqlalchemy import select as sa_select

            ms_result = await db.execute(
                sa_select(UserModelSettings).where(
                    UserModelSettings.user_id == user_id,
                    UserModelSettings.is_active == True,  # noqa: E712
                )
            )
            model_settings = ms_result.scalars().first()
            if model_settings:
                await embed_company_intel(user_id, intel, model_settings)
            else:
                logger.warning(
                    "No active model settings for user %s — skipping pgvector embedding",
                    user_id,
                )
        except Exception as exc:
            logger.warning("Failed to embed company intel in pgvector: %s", exc)

        # --- Persist structured JSON ---
        await save_intel_to_db(db, user_id, intel)

        # --- Log agent run ---
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        await log_agent_run(
            db=db,
            user_id=user_id,
            status="completed",
            input_data={"company_name": company_name, "force_refresh": force_refresh},
            output_data=intel.to_dict(),
            duration_ms=duration_ms,
        )

    return {
        **state,
        "status": "completed",
        "result": intel.to_dict(),
    }
