"""
salary_agent.py — Salary Intelligence & Negotiation Assistant.

LangGraph node that:
1. Queries Exa.ai for real-time salary data
2. Extracts 25th, 50th, 75th percentile figures
3. Classifies user's offer against market percentiles
4. Generates a negotiation script (opening, counter-offer at p75, 2 justifications)
5. Logs run to agent_runs table
6. Returns awaiting_approval for HITL gate on negotiation script

Requirements: 3.1, 3.2, 3.3, 3.4, 3.6, 3.7, 3.8, 3.10
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from enum import Enum

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.core.sync_db import _get_sync_factory, fetch_model_settings
from app.services.exa_service import ExaService

logger = logging.getLogger(__name__)

AGENT_TYPE = "salary_intelligence"

NEGOTIATION_SYSTEM_PROMPT = """You are a salary negotiation expert. Given the role, company,
market salary percentiles, and the candidate's offer classification, generate a negotiation script.

The script MUST contain exactly these sections:
1. "opening" — A confident opening statement for the negotiation conversation
2. "counter_offer" — A specific counter-offer amount set at the 75th percentile value provided
3. "justifications" — Exactly 2 compelling justification points supporting the counter-offer

Return your response as a JSON object with keys: "opening", "counter_offer", "justifications"
(justifications is a list of 2 strings).
Do NOT include markdown fences or any text outside the JSON."""


# ─────────────────────────────────────────────────────────────────────────────
# Pure function: classify offer against market percentiles
# ─────────────────────────────────────────────────────────────────────────────


class OfferClassification(str, Enum):
    """Classification of an offer relative to market percentiles."""

    BELOW_MARKET = "below_market"
    AT_MARKET = "at_market"
    ABOVE_MARKET = "above_market"


def classify_offer(offer: int, p25: int, p50: int, p75: int) -> OfferClassification:
    """Classify offer against market percentiles.

    - below_market: offer < p25
    - above_market: offer > p75
    - at_market: p25 <= offer <= p75 (inclusive on both bounds)

    Args:
        offer: The candidate's offer amount.
        p25: 25th percentile salary.
        p50: 50th percentile salary (median).
        p75: 75th percentile salary.

    Returns:
        OfferClassification enum value.
    """
    if offer < p25:
        return OfferClassification.BELOW_MARKET
    elif offer > p75:
        return OfferClassification.ABOVE_MARKET
    return OfferClassification.AT_MARKET


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _extract_percentiles(salary_results: list[dict]) -> dict[str, int] | None:
    """Extract p25, p50, p75 salary figures from Exa search results.

    Uses a heuristic approach: look for numeric salary data in result snippets.
    If extraction fails, returns None indicating data_unavailable.
    """
    import re

    salary_numbers: list[int] = []

    for result in salary_results:
        text = result.get("text", "") or result.get("snippet", "") or ""
        # Match salary patterns like $120,000 or $120K or 120000
        matches = re.findall(r"\$?([\d,]+)(?:\s*[kK])?\s*(?:per\s+year|/yr|annually|salary)?", text)
        for match in matches:
            num_str = match.replace(",", "")
            try:
                val = int(num_str)
                # Filter reasonable salary values (20k - 1M)
                if 20_000 <= val <= 1_000_000:
                    salary_numbers.append(val)
                elif 20 <= val <= 1000:
                    # Could be in thousands (e.g. "120K")
                    salary_numbers.append(val * 1000)
            except ValueError:
                continue

    if len(salary_numbers) < 3:
        return None

    salary_numbers.sort()
    n = len(salary_numbers)
    p25 = salary_numbers[max(0, n // 4)]
    p50 = salary_numbers[n // 2]
    p75 = salary_numbers[min(n - 1, (3 * n) // 4)]

    return {"p25": p25, "p50": p50, "p75": p75}


def _log_agent_run(
    user_id: str,
    run_id: str,
    status: str,
    input_data: dict,
    output_data: dict | None,
    tokens_used: int | None,
    duration_ms: int,
) -> None:
    """Log run to agent_runs table synchronously (called from thread executor)."""
    from app.models.db import AgentRun

    factory = _get_sync_factory()
    with factory() as db:
        agent_run = AgentRun(
            id=uuid.UUID(run_id),
            user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
            agent_type=AGENT_TYPE,
            status=status,
            input=input_data,
            output=output_data,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
            completed_at=datetime.now(timezone.utc) if status != "running" else None,
        )
        db.add(agent_run)
        db.commit()


def _generate_negotiation_script(
    llm,
    role: str,
    company: str | None,
    p25: int,
    p50: int,
    p75: int,
    classification: str,
) -> dict:
    """Generate negotiation script using LLM.

    Returns dict with: opening, counter_offer, justifications.
    """
    import json

    company_text = f" at {company}" if company else ""
    prompt_content = (
        f"Role: {role}{company_text}\n"
        f"Market Salary Data:\n"
        f"  - 25th percentile: ${p25:,}\n"
        f"  - 50th percentile (median): ${p50:,}\n"
        f"  - 75th percentile: ${p75:,}\n"
        f"Offer classification: {classification}\n"
        f"Counter-offer target: ${p75:,} (75th percentile)\n\n"
        f"Generate the negotiation script."
    )

    response = llm.invoke([
        SystemMessage(content=NEGOTIATION_SYSTEM_PROMPT),
        HumanMessage(content=prompt_content),
    ])

    raw = response.content.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    if raw.endswith("```"):
        raw = raw[:-3]

    try:
        script = json.loads(raw.strip())
    except json.JSONDecodeError:
        # Fallback: construct a basic script
        script = {
            "opening": (
                f"Thank you for the offer. Based on my research of market rates "
                f"for {role} roles, I'd like to discuss the compensation."
            ),
            "counter_offer": p75,
            "justifications": [
                f"Market data shows the 75th percentile for this role is ${p75:,}, reflecting the value I bring.",
                f"My experience and skills position me competitively in the current market for {role} positions.",
            ],
        }

    # Ensure counter_offer is set to p75
    script["counter_offer"] = p75

    # Ensure at least 2 justifications
    if not isinstance(script.get("justifications"), list) or len(script["justifications"]) < 2:
        script["justifications"] = [
            f"Market data shows the 75th percentile for this role is ${p75:,}.",
            f"My qualifications align with top-tier candidates in the {role} space.",
        ]

    return script


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph Node
# ─────────────────────────────────────────────────────────────────────────────


def salary_report_node(state: AgentState) -> AgentState:
    """LangGraph node for salary intelligence and negotiation script generation.

    Expected context keys:
        - role (str): Job title / role
        - company (str, optional): Company name
        - location (str): Location for salary data
        - offer_amount (int, optional): User's current offer for classification

    Returns:
        - On success with data: status=awaiting_approval, pending_action with report + script
        - On data unavailable: status=completed, result with data_unavailable=True
        - On error: status=failed, error message
    """
    import asyncio

    start_time = time.monotonic()
    run_id = state.get("run_id") or str(uuid.uuid4())

    try:
        user_id = state["user_id"]
        context = state["context"]
        role = context.get("role", "")
        company = context.get("company")
        location = context.get("location", "")
        offer_amount = context.get("offer_amount")

        if not role or not location:
            return {
                **state,
                "status": "failed",
                "error": "Both 'role' and 'location' are required in context.",
            }

        # Get user's model settings for LLM routing (Requirement 3.7)
        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            return {
                **state,
                "status": "failed",
                "error": "No active model settings configured for user.",
            }

        # Query Exa for salary data (Requirement 3.1)
        exa_service = ExaService()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Running inside an existing event loop — create new loop in thread
                new_loop = asyncio.new_event_loop()
                try:
                    salary_results = new_loop.run_until_complete(
                        exa_service.search_salary(role, company, location)
                    )
                finally:
                    new_loop.close()
            else:
                salary_results = loop.run_until_complete(
                    exa_service.search_salary(role, company, location)
                )
        except RuntimeError:
            # No event loop available, create one
            salary_results = asyncio.run(
                exa_service.search_salary(role, company, location)
            )

        # Extract percentiles from search results (Requirement 3.2)
        percentiles = _extract_percentiles(salary_results)

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Handle data_unavailable case — HTTP 206 (Requirement 3.8)
        if percentiles is None:
            result = {
                "data_unavailable": True,
                "role": role,
                "company": company,
                "location": location,
                "data_sources": [r.get("url", "") for r in salary_results[:5]],
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }

            _log_agent_run(
                user_id=user_id,
                run_id=run_id,
                status="completed",
                input_data={"role": role, "company": company, "location": location},
                output_data=result,
                tokens_used=None,
                duration_ms=duration_ms,
            )

            return {
                **state,
                "status": "completed",
                "result": result,
            }

        p25, p50, p75 = percentiles["p25"], percentiles["p50"], percentiles["p75"]

        # Classify offer if provided (Requirement 3.3)
        classification = None
        if offer_amount is not None:
            classification = classify_offer(offer_amount, p25, p50, p75).value

        # Build LLM and generate negotiation script (Requirements 3.4, 3.7)
        llm = _build_llm(model_settings)
        script = _generate_negotiation_script(
            llm, role, company, p25, p50, p75, classification or "at_market"
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)

        report = {
            "p25": p25,
            "p50": p50,
            "p75": p75,
            "offer_amount": offer_amount,
            "classification": classification,
            "data_sources": [r.get("url", "") for r in salary_results[:5]],
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "company": company,
            "location": location,
        }

        # Log run to agent_runs (Requirement 3.6)
        _log_agent_run(
            user_id=user_id,
            run_id=run_id,
            status="awaiting_approval",
            input_data={
                "role": role,
                "company": company,
                "location": location,
                "offer_amount": offer_amount,
            },
            output_data={"report": report, "script": script},
            tokens_used=None,  # Token tracking handled by LangChain callbacks
            duration_ms=duration_ms,
        )

        # Return awaiting_approval for HITL gate (Requirement 3.10)
        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": {
                "type": "salary_report_review",
                "report": report,
                "script": script,
            },
            "result": report,
            "messages": state["messages"] + [
                AIMessage(content=f"Salary report generated for {role} in {location}.")
            ],
        }

    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error("Salary agent failed for user %s: %s", state.get("user_id"), exc)
        return {**state, "status": "failed", "error": str(exc)}
