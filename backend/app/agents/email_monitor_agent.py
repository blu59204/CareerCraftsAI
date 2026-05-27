"""
email_monitor_agent.py — Monitors Gmail inbox for job-related notifications.

Reads emails from hiring platforms (LinkedIn, Naukri, Indeed, etc.) and:
1. Detects interview invites → updates application status to "interview"
2. Detects rejections → updates status to "rejected"
3. Detects "profile viewed" → updates status to "viewed"
4. Detects recruiter messages → flags for user attention
5. Triggers follow-up scheduling when appropriate

Runs as a scheduled task (via BullMQ or direct invocation).
"""
import logging
import re
import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage

from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings
from app.services.gmail_service import GmailMCPClient

logger = logging.getLogger(__name__)

# Platform sender patterns
_PLATFORM_SENDERS = {
    "linkedin": ["linkedin.com", "notifications-noreply@linkedin.com"],
    "naukri": ["naukri.com", "info@naukri.com"],
    "indeed": ["indeed.com", "alert@indeed.com"],
    "foundit": ["foundit.in", "monster.com"],
    "instahyre": ["instahyre.com"],
    "glassdoor": ["glassdoor.com"],
}

# Status detection patterns
_STATUS_PATTERNS = {
    "interview": [
        r"interview\s+(scheduled|invitation|invite)",
        r"schedule.*interview",
        r"would like to.*interview",
        r"shortlisted.*for.*interview",
        r"next\s+round",
    ],
    "rejected": [
        r"unfortunately.*not.*moving\s+forward",
        r"decided.*not.*proceed",
        r"position.*has.*been.*filled",
        r"not.*selected",
        r"regret.*inform",
        r"will\s+not\s+be\s+moving\s+forward",
    ],
    "viewed": [
        r"viewed\s+your\s+(profile|application|resume)",
        r"recruiter.*viewed",
        r"your\s+application.*viewed",
    ],
    "shortlisted": [
        r"shortlisted",
        r"selected.*for.*next",
        r"profile.*matches",
    ],
}

_CLASSIFY_PROMPT = """Classify this email notification from a job platform.

From: {sender}
Subject: {subject}
Body (first 500 chars): {body}

Respond with EXACTLY one of these categories:
- INTERVIEW: Interview scheduled or invitation
- REJECTED: Application rejected
- VIEWED: Profile/application viewed by recruiter
- SHORTLISTED: Shortlisted for next round
- RECRUITER_MESSAGE: Direct message from a recruiter
- IRRELEVANT: Marketing, job alerts, or unrelated

Also extract the company name if mentioned.

Format: CATEGORY | COMPANY: <name or UNKNOWN>"""


def email_monitor_node(state: AgentState) -> AgentState:
    """Agent node that scans Gmail for job notifications and classifies them."""
    try:
        user_id = state["user_id"]
        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings configured")

        gmail = GmailMCPClient(user_id)

        # Search for recent job-related emails
        queries = [
            "from:linkedin.com newer_than:1d",
            "from:naukri.com newer_than:1d",
            "from:indeed.com newer_than:1d",
            "subject:interview newer_than:3d",
            "subject:application newer_than:3d",
        ]

        all_notifications: list[dict] = []
        for query in queries:
            results = gmail.search_threads(query, max_results=5)
            if isinstance(results, list):
                all_notifications.extend(results)

        if not all_notifications:
            return {
                **state,
                "status": "completed",
                "result": {"notifications": [], "updates": []},
            }

        # Classify each notification
        llm = _build_llm(model_settings)
        updates: list[dict] = []

        for notif in all_notifications[:15]:  # Cap to avoid token burn
            classification = _classify_notification(notif, llm)
            if classification and classification["category"] != "IRRELEVANT":
                updates.append(classification)

        return {
            **state,
            "status": "completed",
            "result": {
                "notifications_scanned": len(all_notifications),
                "updates": updates,
            },
        }
    except Exception as exc:
        logger.error("Email monitor failed for user %s: %s", state.get("user_id"), exc)
        return {**state, "status": "failed", "error": str(exc)}


def _classify_notification(notif: dict, llm) -> dict | None:
    """Classify a single email notification."""
    # Try regex first (cheaper than LLM)
    subject = str(notif.get("subject", notif.get("snippet", "")))
    body = str(notif.get("body", notif.get("snippet", "")))[:500]
    sender = str(notif.get("from", notif.get("sender", "")))

    # Quick regex classification
    combined = f"{subject} {body}".lower()
    for status, patterns in _STATUS_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                company = _extract_company_regex(combined)
                return {
                    "category": status.upper(),
                    "company": company,
                    "subject": subject[:100],
                    "sender": sender,
                }

    # Fall back to LLM for ambiguous cases
    try:
        response = llm.invoke([HumanMessage(
            content=_CLASSIFY_PROMPT.format(sender=sender, subject=subject, body=body)
        )])
        text = response.content.strip()
        parts = text.split("|")
        category = parts[0].strip()
        company = "UNKNOWN"
        if len(parts) > 1 and "COMPANY:" in parts[1]:
            company = parts[1].split("COMPANY:")[1].strip()

        if category in ("INTERVIEW", "REJECTED", "VIEWED", "SHORTLISTED", "RECRUITER_MESSAGE"):
            return {
                "category": category,
                "company": company,
                "subject": subject[:100],
                "sender": sender,
            }
    except Exception as exc:
        logger.debug("LLM classification failed: %s", exc)

    return None


def _extract_company_regex(text: str) -> str:
    """Try to extract company name from email text."""
    # Common patterns: "at <Company>", "from <Company>", "<Company> has"
    patterns = [
        r"at\s+([A-Z][A-Za-z0-9\s&.]+?)(?:\s+has|\s+is|\s+would|\.|,)",
        r"from\s+([A-Z][A-Za-z0-9\s&.]+?)(?:\s+has|\s+is|\.|,)",
    ]
    for p in patterns:
        match = re.search(p, text)
        if match:
            return match.group(1).strip()
    return "UNKNOWN"


async def run_email_monitor(user_id: str) -> dict:
    """Convenience function to run the email monitor and update application statuses."""
    from app.core.database import AsyncSessionLocal
    from app.models.db import JobApplication
    from sqlalchemy import select, update

    state = AgentState(
        user_id=user_id,
        run_id=str(uuid.uuid4()),
        task_type="email_monitor",
        messages=[HumanMessage(content="Scan inbox for job notifications")],
        context={},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )

    import asyncio
    result_state = await asyncio.get_event_loop().run_in_executor(
        None, email_monitor_node, state
    )

    if result_state["status"] != "completed":
        return {"status": "failed", "error": result_state.get("error")}

    updates = (result_state.get("result") or {}).get("updates", [])
    status_map = {
        "INTERVIEW": "interview",
        "REJECTED": "rejected",
        "VIEWED": "viewed",
        "SHORTLISTED": "shortlisted",
    }

    updated_count = 0
    async with AsyncSessionLocal() as db:
        for update_item in updates:
            new_status = status_map.get(update_item["category"])
            if not new_status or update_item["company"] == "UNKNOWN":
                continue

            # Find matching application by company name
            res = await db.execute(
                select(JobApplication).where(
                    JobApplication.user_id == uuid.UUID(user_id),
                    JobApplication.company.ilike(f"%{update_item['company']}%"),
                    JobApplication.status.in_(["applied", "viewed", "shortlisted"]),
                )
            )
            app = res.scalars().first()
            if app:
                app.status = new_status
                updated_count += 1

        await db.commit()

    return {
        "status": "ok",
        "notifications_scanned": (result_state.get("result") or {}).get("notifications_scanned", 0),
        "updates_found": len(updates),
        "applications_updated": updated_count,
    }
