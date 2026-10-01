"""Recently funded companies, read from public startup-news RSS feeds.

A company that just raised money is hiring, so its jobs get a small boost in
ranking and a visible reason. Only headlines of the form "<Company> raises
..." are used. Names are kept in Redis for 45 days. Feeds come from
FUNDING_FEEDS (empty disables the signal); any failure is ignored because it
only ever adds a bonus.
"""

from __future__ import annotations

import asyncio
import logging
import re

from app.core.config import settings
from app.services.job_connectors import _squash
from app.services.public_http import public_get

logger = logging.getLogger(__name__)

KEY = "funding:company:"
REFRESHED = "funding:refreshed"
TTL_SECONDS = 45 * 86400
REFRESH_SECONDS = 6 * 3600
BONUS = 5
_background: set[asyncio.Task] = set()
_HEADLINE = re.compile(
    r"^(?P<company>[A-Z0-9][\w&.\-' ]{1,40}?)\s+"
    r"(?:raises|bags|secures|lands|closes|snags|nets)\b",
)


def company_from_headline(title: str) -> str | None:
    match = _HEADLINE.match((title or "").strip())
    if not match:
        return None
    name = match.group("company").strip()
    # "Startup X" style prefixes and one-word stop words are not companies
    return name if _squash(name) and len(name.split()) <= 4 else None


def parse_feed(xml_text: str) -> list[str]:
    from defusedxml import ElementTree

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []
    names = (company_from_headline(item.findtext("title") or "") for item in root.iter("item"))
    return [name for name in names if name]


async def _redis():
    from app.services.token_budget_service import _get_redis

    return await _get_redis()


async def refresh() -> int:
    """Read the feeds and remember the companies. Returns how many."""
    feeds = settings.FUNDING_FEEDS[:5]
    if not feeds:
        return 0
    redis = await _redis()
    if not await redis.set(REFRESHED, "1", nx=True, ex=REFRESH_SECONDS):
        return 0
    found = 0
    for url in feeds:
        try:
            response = await public_get(url, max_bytes=2_000_000)
            response.raise_for_status()
        except Exception:
            logger.info("Funding feed unavailable: %s", url)
            continue
        for name in parse_feed(response.text):
            await redis.set(KEY + _squash(name), name, ex=TTL_SECONDS)
            found += 1
    return found


async def funded_among(companies: list[str]) -> set[str]:
    """The squashed names, out of these companies, that raised recently."""
    if not settings.FUNDING_FEEDS or not companies:
        return set()
    try:
        # Refreshing reads outside feeds, so it runs in the background and
        # never delays a search; this search uses what is already stored.
        task = asyncio.create_task(refresh())
        _background.add(task)
        task.add_done_callback(_background.discard)
        redis = await _redis()
        keys = sorted({_squash(c) for c in companies if _squash(c)})
        values = await redis.mget([KEY + k for k in keys])
        return {k for k, v in zip(keys, values, strict=True) if v}
    except Exception:
        logger.info("Funding signal unavailable", exc_info=True)
        return set()
