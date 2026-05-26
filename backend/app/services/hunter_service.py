"""
hunter_service.py — Email finder via Hunter.io API.

Finds recruiter/hiring manager emails from company domains.
Used in the auto-apply pipeline to discover cold email targets.
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

HUNTER_API_BASE = "https://api.hunter.io/v2"


class HunterService:
    """Hunter.io email discovery service."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or getattr(settings, "HUNTER_API_KEY", "")

    async def find_email(self, domain: str, first_name: str = "", last_name: str = "") -> dict | None:
        """Find a specific person's email at a domain.

        Returns: {"email": "...", "confidence": 95, "type": "personal"} or None
        """
        if not self.api_key:
            logger.warning("HUNTER_API_KEY not configured")
            return None

        params = {"domain": domain, "api_key": self.api_key}
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{HUNTER_API_BASE}/email-finder", params=params)
                resp.raise_for_status()
                data = resp.json().get("data", {})
                if data.get("email"):
                    return {
                        "email": data["email"],
                        "confidence": data.get("confidence", 0),
                        "type": data.get("type", "unknown"),
                    }
        except Exception as exc:
            logger.warning("Hunter email-finder failed for %s: %s", domain, exc)
        return None

    async def domain_search(self, domain: str, department: str = "hr") -> list[dict]:
        """Search all emails at a domain, filtered by department.

        Returns list of: {"email": "...", "first_name": "...", "last_name": "...", "position": "...", "confidence": 95}
        """
        if not self.api_key:
            logger.warning("HUNTER_API_KEY not configured")
            return []

        params = {
            "domain": domain,
            "api_key": self.api_key,
            "department": department,
            "limit": 10,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{HUNTER_API_BASE}/domain-search", params=params)
                resp.raise_for_status()
                data = resp.json().get("data", {})
                emails = data.get("emails", [])
                return [
                    {
                        "email": e["value"],
                        "first_name": e.get("first_name", ""),
                        "last_name": e.get("last_name", ""),
                        "position": e.get("position", ""),
                        "confidence": e.get("confidence", 0),
                    }
                    for e in emails
                    if e.get("value")
                ]
        except Exception as exc:
            logger.warning("Hunter domain-search failed for %s: %s", domain, exc)
            return []

    async def find_recruiter_email(self, company: str, job_url: str = "") -> dict | None:
        """High-level: find the best recruiter email for a company.

        Tries domain search with HR/recruiting department filter.
        Returns the highest-confidence result.
        """
        # Extract domain from company name (simplified)
        domain = company.lower().replace(" ", "").replace(",", "") + ".com"

        # Try HR department first
        results = await self.domain_search(domain, department="hr")
        if not results:
            # Fallback: try executive department
            results = await self.domain_search(domain, department="executive")
        if not results:
            # Fallback: general search
            results = await self.domain_search(domain, department="")

        if results:
            # Return highest confidence
            results.sort(key=lambda x: x["confidence"], reverse=True)
            return results[0]
        return None
