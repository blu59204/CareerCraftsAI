"""Keyless public-web lookups for research agents.

Used when no paid search provider (Exa, Firecrawl) is configured, or when
one returns nothing: Wikipedia for a company overview, Google News RSS for
recent headlines, and DuckDuckGo's HTML endpoint for general snippets.
Every helper returns an empty result instead of raising — callers treat a
missing source as a gap, not a failure of the whole run.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import httpx
from defusedxml import ElementTree

logger = logging.getLogger(__name__)

TIMEOUT_S = 12.0
USER_AGENT = "Mozilla/5.0 (compatible; CareerCraftAI/1.0; research)"
# Wikimedia asks API clients to identify themselves with a contact URL.
WIKI_AGENT = "CareerCraftAI/1.0 (+https://github.com/blu59204/careercraftsai) httpx"

# Words a Wikipedia lead uses for an organisation, to tell "Stripe (company)"
# from the stripe pattern or a disambiguation page.
_ORG_WORDS = (
    "company",
    "corporation",
    "multinational",
    "conglomerate",
    "startup",
    "firm",
    "business",
    "organization",
    "organisation",
    "provider",
    "developer",
    "manufacturer",
    "retailer",
    "bank",
    "brand",
    "subsidiary",
    "enterprise",
    "platform",
    "inc.",
    "ltd",
    "llc",
    "limited",
)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def mentions(company_name: str, text: str) -> bool:
    """True when every word of the company name appears in the text."""
    words = _normalize(company_name).split()
    haystack = f" {_normalize(text)} "
    return bool(words) and all(f" {w} " in haystack for w in words)


async def wikipedia_summary(company_name: str) -> dict[str, Any] | None:
    """Lead section of the company's English Wikipedia article, if it has one.

    One request: a search generator returning plain-text intro extracts, so
    we stay well inside Wikimedia's API etiquette.
    """
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_S, headers={"User-Agent": WIKI_AGENT}
        ) as client:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": f"{company_name} company",
                    "gsrlimit": 5,
                    "prop": "extracts|pageprops",
                    "exintro": 1,
                    "explaintext": 1,
                    "exlimit": 5,
                    "redirects": 1,
                    "format": "json",
                    "formatversion": 2,
                },
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", [])
    except Exception as exc:  # network, JSON, rate limit — all just "no data"
        logger.info("Wikipedia lookup failed for %r: %s", company_name, exc)
        return None

    for page in sorted(pages, key=lambda p: p.get("index", 99)):
        title = page.get("title", "")
        extract = (page.get("extract") or "").strip()
        if "disambiguation" in (page.get("pageprops") or {}) or not extract:
            continue
        if not mentions(company_name, title):
            continue
        if not any(word in extract.lower() for word in _ORG_WORDS):
            continue
        return {
            "content": extract,
            "source": "wikipedia",
            "url": "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_")),
        }
    return None


async def google_news(company_name: str, limit: int = 5) -> list[dict[str, Any]]:
    """Recent headlines naming the company, from the public Google News RSS feed."""
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True
        ) as client:
            resp = await client.get(
                "https://news.google.com/rss/search",
                params={"q": f'"{company_name}"', "hl": "en-US", "gl": "US", "ceid": "US:en"},
            )
            resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)
    except Exception as exc:
        logger.info("Google News lookup failed for %r: %s", company_name, exc)
        return []

    items: list[dict[str, Any]] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        # Headlines arrive as "Headline - Publisher".
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].strip()
        if not title or not mentions(company_name, title):
            continue
        items.append(
            {
                "title": title,
                "url": (item.findtext("link") or "").strip(),
                "snippet": source,
                "published": (item.findtext("pubDate") or "").strip(),
            }
        )
        if len(items) >= limit:
            break
    return items


async def duckduckgo(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Organic results (title, url, snippet) from DuckDuckGo's HTML endpoint."""
    try:
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(
            timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True
        ) as client:
            resp = await client.post(
                "https://html.duckduckgo.com/html/", data={"q": query, "kl": "us-en"}
            )
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.info("DuckDuckGo lookup failed for %r: %s", query, exc)
        return []

    results: list[dict[str, str]] = []
    for node in soup.select(".result"):
        link = node.select_one("a.result__a")
        if link is None:
            continue
        href = link.get("href", "")
        if "uddg=" in href:  # DDG wraps the target: /l/?uddg=<url>
            href = (parse_qs(urlparse(href).query).get("uddg") or [""])[0]
        snippet = node.select_one(".result__snippet")
        title = link.get_text(" ", strip=True)
        if not title or not href.startswith("http"):
            continue
        results.append(
            {
                "title": title,
                "url": href,
                "snippet": snippet.get_text(" ", strip=True) if snippet else "",
            }
        )
        if len(results) >= limit:
            break
    return results
