"""Public-only GitHub evidence. OAuth stays in Nango; no README enters a prompt."""

from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import text

from app.integrations.factory import build_integration_gateway
from app.integrations.repository import get_connection
from app.services.jobs_database import AsyncSessionLocal
from app.services.public_http import public_get


def public_login(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use https://github.com/username")
    login = parsed.path.strip("/")
    if parsed.path not in {"/" + login, "/" + login + "/"}:
        raise ValueError("Use a public GitHub profile URL")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", login):
        raise ValueError("Use a public GitHub profile URL")
    return login


def analyze(repos: list[dict]) -> dict:
    skills, projects = {}, []
    frameworks = {
        "react": "React",
        "next.js": "Next.js",
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "tensorflow": "TensorFlow",
        "pytorch": "PyTorch",
        "vue": "Vue",
        "angular": "Angular",
        "langgraph": "LangGraph",
    }
    for repo in repos:
        if (
            repo.get("private")
            or repo.get("visibility", "public") != "public"
            or repo.get("fork")
            or repo.get("archived")
        ):
            continue
        url = repo.get("html_url", "")
        if not url.startswith("https://github.com/"):
            continue
        languages = repo.get("languages") or {}
        names = list(languages)
        readme = repo.get("readme", "").lower()
        names += [
            name
            for keyword, name in frameworks.items()
            if re.search(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", readme)
        ]
        for name in dict.fromkeys(names):
            category = "language" if name in languages else "framework"
            evidence = {
                "url": url,
                "kind": (
                    (
                        "language_bytes"
                        if languages.get(name) is not None
                        else "primary_language"
                    )
                    if category == "language"
                    else "readme_mention"
                ),
                "bytes": languages.get(name),
                "verified": category == "language",
            }
            skills.setdefault(
                name,
                {
                    "name": name,
                    "category": category,
                    "confidence": (
                        "repository_evidence"
                        if category == "language"
                        else "self_reported_readme"
                    ),
                    "evidence": [],
                },
            )["evidence"].append(evidence)
        try:
            pushed = datetime.fromisoformat(
                str(repo.get("pushed_at") or "").replace("Z", "+00:00")
            )
            if pushed.tzinfo is None:
                pushed = pushed.replace(tzinfo=UTC)
            recent_push = pushed >= datetime.now(UTC) - timedelta(days=90)
        except ValueError:
            recent_push = False
        score = (
            min(20, len(names) * 3)
            + min(20, repo.get("stargazers_count", 0))
            + (10 if recent_push else 0)
            + min(10, repo.get("recent_events", 0))
        )
        projects.append(
            {
                "name": repo["name"],
                "url": url,
                "description": (repo.get("description") or "")[:500] or None,
                "languages": list(languages),
                "updated_at": repo.get("pushed_at"),
                "score": score,
                "reason": "Public owned repository; "
                + (", ".join(names[:6]) if names else "no technology evidence")
                + f"; {repo.get('recent_events',0)} recent public activity events",
            }
        )
    projects.sort(
        key=lambda item: (item["score"], item["updated_at"] or "", item["name"]),
        reverse=True,
    )
    return {
        "skills": sorted(skills.values(), key=lambda item: item["name"]),
        "top_repos": projects[:10],
        "suggested_projects": [p for p in projects if p["languages"]][:5],
    }


async def _public(path: str):
    response = await public_get(
        "https://api.github.com/" + path,
        headers={"Accept": "application/vnd.github+json"},
        max_bytes=2_000_000,
    )
    if response.status_code in {403, 429}:
        raise ValueError("GitHub rate limit reached; try later or connect with Nango")
    response.raise_for_status()
    return response.json()


async def refresh_profile(user_id: uuid.UUID, url: str | None = None) -> dict:
    async with AsyncSessionLocal() as db:
        state = (
            (
                await db.execute(
                    text("SELECT * FROM github_profiles WHERE user_id=:uid FOR UPDATE"),
                    {"uid": user_id},
                )
            )
            .mappings()
            .first()
        )
        connection = await get_connection(db, user_id=user_id, provider="github")
        oauth = bool(connection and connection.status == "connected" and url is None)
        login = (
            public_login(url)
            if url
            else (
                state["login"]
                if state and state["mode"] == "public_url" and not state["deleted_at"]
                else None
            )
        )
        same_identity = state and (
            url is None or (state["mode"] == "public_url" and state["login"] == login)
        )
        if (
            same_identity
            and state["next_allowed_at"]
            and state["next_allowed_at"] > datetime.now(UTC)
        ):
            connected = state["mode"] == "public_url" or oauth
            if connected and state["data"] and not state["deleted_at"]:
                return state["data"]
            if not connected:
                raise LookupError("GitHub is not connected")
            raise ValueError("GitHub refresh is rate limited; try later")
        if not oauth and not login:
            raise LookupError("GitHub is not connected")
        revision = (
            await db.execute(
                text(
                    """INSERT INTO github_profiles(user_id,mode,login,next_allowed_at,version)
            VALUES(:uid,:mode,:login,:lease,1) ON CONFLICT(user_id) DO UPDATE
            SET next_allowed_at=EXCLUDED.next_allowed_at,
            version=github_profiles.version+1,deleted_at=NULL RETURNING version"""
                ),
                {
                    "uid": user_id,
                    "mode": "nango" if oauth else "public_url",
                    "login": login or "",
                    "lease": datetime.now(UTC) + timedelta(minutes=5),
                },
            )
        ).scalar_one()
        await db.commit()
    gateway = build_integration_gateway() if oauth else None

    async def fetch(path):
        if gateway:
            result = await gateway.proxy_request(
                user_id=user_id,
                provider="github",
                method="GET",
                path=path,
                headers={"Accept": "application/vnd.github+json"},
            )
            if result.status_code >= 400:
                raise ValueError("GitHub request failed or is rate limited")
            return result.data
        return await _public(path)

    try:
        if oauth:
            account = await fetch("user")
            login = account.get("login") if isinstance(account, dict) else None
            if not login or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
                raise ValueError("GitHub profile is unavailable")
        repos = await fetch(f"users/{login}/repos?type=owner&sort=updated&per_page=100")
        if not isinstance(repos, list):
            raise ValueError("Invalid repository response")
        events = await fetch(f"users/{login}/events/public?per_page=100")
        counts = {}
        for event in events if isinstance(events, list) else []:
            posted = event.get("created_at")
            try:
                if not posted or datetime.fromisoformat(
                    posted.replace("Z", "+00:00")
                ) < datetime.now(UTC) - timedelta(days=90):
                    continue
            except (ValueError, TypeError):
                continue
            name = (event.get("repo") or {}).get("name", "")
            counts[name] = counts.get(name, 0) + 1
        enriched = []
        for index, repo in enumerate(repos[:100]):
            owner = (repo.get("owner") or {}).get("login", "")
            if (
                owner.casefold() != login.casefold()
                or repo.get("private")
                or repo.get("visibility", "public") != "public"
                or repo.get("fork")
                or repo.get("archived")
            ):
                continue
            name = repo.get("name", "")
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name):
                continue
            # Public-only paths remain fixed even if the OAuth grant is mistakenly broad.
            base = f"repos/{login}/{name}"
            primary = repo.get("language")
            languages = {primary: None} if isinstance(primary, str) and primary else {}
            if index < 12:
                languages = await fetch(base + "/languages")
            readme = ""
            try:
                data = await fetch(base + "/readme") if index < 12 else None
                if isinstance(data, dict) and data.get("encoding") == "base64":
                    readme = base64.b64decode(
                        str(data.get("content", ""))[:180000], validate=False
                    ).decode("utf-8", errors="replace")[:32000]
            except Exception as exc:
                logging.getLogger(__name__).info(
                    "github_readme_unavailable",
                    extra={"error_type": type(exc).__name__},
                )
            enriched.append(
                {
                    "name": name,
                    "html_url": repo.get("html_url"),
                    "description": repo.get("description"),
                    "private": False,
                    "visibility": "public",
                    "languages": languages if isinstance(languages, dict) else {},
                    "readme": readme,
                    "pushed_at": repo.get("pushed_at"),
                    "stargazers_count": int(repo.get("stargazers_count") or 0),
                    "recent_events": counts.get(f"{login}/{name}", 0),
                }
            )
        data = analyze(enriched)
        async with AsyncSessionLocal() as db:
            # A disconnect/delete while fetching must win over a late refresh.
            current = (
                (
                    await db.execute(
                        text(
                            "SELECT deleted_at,version FROM github_profiles "
                            "WHERE user_id=:uid FOR UPDATE"
                        ),
                        {"uid": user_id},
                    )
                )
                .mappings()
                .first()
            )
            if not current or current["deleted_at"] or current["version"] != revision:
                raise LookupError("GitHub connection changed while refreshing")
            await db.execute(
                text(
                    """UPDATE github_profiles SET mode=:mode,login=:login,data=CAST(:data AS jsonb),
                refreshed_at=now(),next_allowed_at=now()+interval '24 hours',deleted_at=NULL
                WHERE user_id=:uid"""
                ),
                {
                    "uid": user_id,
                    "mode": "nango" if oauth else "public_url",
                    "login": login,
                    "data": json.dumps(data),
                },
            )
            await db.commit()
        return data
    finally:
        if gateway and hasattr(gateway, "aclose"):
            await gateway.aclose()


async def get_profile(user_id: uuid.UUID) -> dict | None:
    async with AsyncSessionLocal() as db:
        state = (
            (
                await db.execute(
                    text(
                        "SELECT mode,data,deleted_at FROM github_profiles WHERE user_id=:uid"
                    ),
                    {"uid": user_id},
                )
            )
            .mappings()
            .first()
        )
        if not state or state["deleted_at"] or not state["data"]:
            return None
        if state["mode"] == "nango":
            connection = await get_connection(db, user_id=user_id, provider="github")
            if not connection or connection.status != "connected":
                return None
        return state["data"]


async def delete_profile(user_id: uuid.UUID):
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("""INSERT INTO github_profiles(user_id,mode,login,deleted_at,data)
            VALUES(:uid,'public_url','',now(),NULL) ON CONFLICT(user_id) DO UPDATE
            SET deleted_at=now(),data=NULL,login='',next_allowed_at=NULL,
            version=github_profiles.version+1"""),
            {"uid": user_id},
        )
        await db.commit()
