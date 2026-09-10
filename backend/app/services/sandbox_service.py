"""OpenSandbox lifecycle and tenant-scoped, encrypted browser session state.

CDP endpoints and infrastructure credentials stay server-side. The API exposes
authenticated screenshots/input, not a public debugging port.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

import httpx
from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import decrypt_api_key, encrypt_api_key
from app.models.db import AgentRun, BrowserAccountState, BrowserSession


def allowed_domains() -> list[str]:
    return [s.strip().lower() for s in settings.SANDBOX_ALLOWED_DOMAINS.split(",") if s.strip()]


def validate_browser_url(url: str) -> str:
    import ipaddress
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Browser destinations must be HTTPS without credentials or custom ports")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP address destinations are not supported")
    if not host or not any(
        host == domain or (domain.startswith("*.") and host.endswith(domain[1:]))
        for domain in allowed_domains()
    ):
        raise ValueError("This portal is not in SANDBOX_ALLOWED_DOMAINS")
    return url


class OpenSandboxProvider:
    """Adapter for the documented /v1/sandboxes lifecycle API."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client

    async def request(self, method: str, path: str, **kwargs):
        if not settings.OPEN_SANDBOX_URL or not settings.OPEN_SANDBOX_API_KEY:
            raise RuntimeError("OpenSandbox is not configured")
        url = settings.OPEN_SANDBOX_URL.rstrip("/") + "/v1" + path
        headers = {"OPEN-SANDBOX-API-KEY": settings.OPEN_SANDBOX_API_KEY}
        if self.client:
            response = await self.client.request(method, url, headers=headers, **kwargs)
        else:
            async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
        if method == "DELETE" and response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json() if response.content else {}

    async def create(self, session: BrowserSession) -> str:
        if not allowed_domains():
            raise ValueError("Configure allowed portal, identity and CDN domains first")
        result = await self.request("POST", "/sandboxes", json={
            "image": {"uri": settings.OPEN_SANDBOX_CHROME_IMAGE},
            "entrypoint": ["/opt/browser/start.sh"],
            "timeout": settings.SANDBOX_TTL_SECONDS,
            "resourceLimits": {"cpu": settings.SANDBOX_CPU, "memory": settings.SANDBOX_MEMORY},
            "metadata": {"app": "careercraft", "session": str(session.id)},
            "networkPolicy": {
                "defaultAction": "deny",
                "egress": [{"action": "allow", "target": domain} for domain in allowed_domains()],
            },
        })
        return result["id"]

    async def destroy(self, sandbox_id: str) -> None:
        await self.request("DELETE", f"/sandboxes/{sandbox_id}")

    async def endpoint(self, sandbox_id: str) -> tuple[str, dict]:
        result = await self.request("GET", f"/sandboxes/{sandbox_id}/endpoints/9222")
        endpoint = result["endpoint"]
        if "://" not in endpoint:
            endpoint = urlparse(settings.OPEN_SANDBOX_URL).scheme + "://" + endpoint
        return endpoint.rstrip("/"), result.get("headers") or {}

    async def cdp(self, sandbox_id: str) -> tuple[str, dict]:
        endpoint, headers = await self.endpoint(sandbox_id)
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            for attempt in range(10):
                try:
                    response = await client.get(endpoint + "/json/version", headers=headers)
                    response.raise_for_status()
                    remote = urlparse(response.json()["webSocketDebuggerUrl"])
                    base = urlparse(endpoint)
                    # Chromium advertises localhost; use the provider's trusted routing endpoint.
                    ws = urlunparse(("wss" if base.scheme == "https" else "ws", base.netloc,
                                     base.path.rstrip("/") + remote.path, "", "", ""))
                    return ws, headers
                except (httpx.HTTPError, KeyError):
                    if attempt == 9:
                        raise
                    await asyncio.sleep(1)
        raise RuntimeError("Browser did not become ready")


async def acquire_session(user_id: str, run_id: str) -> BrowserSession:
    from app.services.workflow_service import CapacityUnavailable
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        # Brief global admission transaction, never held during provision/network I/O.
        await db.execute(text("SELECT pg_advisory_xact_lock(73001942)"))
        run = await db.get(AgentRun, uuid.UUID(run_id))
        if not run or str(run.user_id) != str(user_id):
            raise PermissionError("Run ownership mismatch")
        existing = (await db.execute(select(BrowserSession).where(
            BrowserSession.run_id == run.id,
        ))).scalar_one_or_none()
        if existing:
            if existing.expires_at <= now or existing.status in {"closed", "failed", "closing"}:
                raise RuntimeError("Browser session expired; prepare a new application for review")
            if not existing.sandbox_id or existing.status == "provisioning":
                # Another worker is still provisioning; back off and retry.
                raise CapacityUnavailable("Browser provisioning has not completed")
            if existing.expires_at <= now + timedelta(seconds=30):
                raise RuntimeError("Browser session expired; prepare a new application for review")
            return existing
        active = select(BrowserSession).where(
            BrowserSession.status.not_in(["closed", "failed"]), BrowserSession.expires_at > now,
        )
        count = (await db.execute(select(func.count()).select_from(active.subquery()))).scalar_one()
        user_active = (await db.execute(active.where(BrowserSession.user_id == run.user_id))).scalars().first()
        if count >= settings.SANDBOX_MAX_ACTIVE or user_active:
            raise CapacityUnavailable("Browser capacity is occupied")
        session = BrowserSession(id=uuid.uuid4(), run_id=run.id, user_id=run.user_id,
                                 status="provisioning", expires_at=now + timedelta(seconds=settings.SANDBOX_TTL_SECONDS))
        db.add(session)
        await db.commit()
    provider = OpenSandboxProvider()
    sandbox_id = None
    try:
        sandbox_id = await provider.create(session)
        # Store identifier before readiness checks, so the reaper can clean failures.
        async with AsyncSessionLocal() as db:
            saved = await db.get(BrowserSession, session.id)
            saved.sandbox_id = sandbox_id
            await db.commit()
        session.sandbox_id = sandbox_id
        async with browser_page(session) as (context, page):
            async with AsyncSessionLocal() as db:
                account = await db.get(BrowserAccountState, session.user_id)
            if account:
                state = json.loads(decrypt_api_key(account.state_enc, settings.APP_SECRET_KEY))
                await context.add_cookies(state.get("cookies", []))
                # Restore origin-localStorage only on its own origin, never on unrelated pages.
                origins = json.dumps(state.get("origins", []))
                await context.add_init_script(f"""(() => {{
                    const item = ({origins}).find(x => x.origin === location.origin);
                    if (item) for (const entry of item.localStorage || []) {{
                        if (localStorage.getItem(entry.name) === null) localStorage.setItem(entry.name, entry.value);
                    }}
                }})()""")
        async with AsyncSessionLocal() as db:
            saved = await db.get(BrowserSession, session.id)
            saved.status = "ready"
            await db.commit()
        session.status = "ready"
        return session
    except BaseException:
        async with AsyncSessionLocal() as db:
            saved = await db.get(BrowserSession, session.id)
            saved.status = "closing" if sandbox_id else "failed"
            await db.commit()
        raise


@asynccontextmanager
async def browser_page(session: BrowserSession):
    from playwright.async_api import async_playwright
    if not session.sandbox_id or session.expires_at <= datetime.now(timezone.utc):
        raise RuntimeError("Browser session unavailable or expired")
    ws, headers = await OpenSandboxProvider().cdp(session.sandbox_id)
    driver = None
    try:
        driver = await async_playwright().start()
        browser = await driver.chromium.connect_over_cdp(ws, headers=headers or None, timeout=20000)
        context = browser.contexts[0]
        page = context.pages[-1] if context.pages else await context.new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        yield context, page
    finally:
        # Disconnect this controller, leave Chromium and the review page alive.
        if driver is not None:
            await driver.stop()


async def save_account_state(session: BrowserSession, context) -> None:
    state = await context.storage_state()
    encrypted = encrypt_api_key(json.dumps(state), settings.APP_SECRET_KEY)
    async with AsyncSessionLocal() as db:
        account = await db.get(BrowserAccountState, session.user_id)
        if account:
            account.state_enc = encrypted
        else:
            db.add(BrowserAccountState(user_id=session.user_id, state_enc=encrypted))
        await db.commit()


async def reap_sessions() -> None:
    if not settings.OPEN_SANDBOX_URL:
        return
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(BrowserSession).join(AgentRun).where(
            BrowserSession.status.not_in(["closed", "failed"]),
            (BrowserSession.expires_at <= datetime.now(timezone.utc)) |
            (BrowserSession.status == "closing") |
            AgentRun.status.in_(["completed", "failed"]),
        ).limit(10).with_for_update(skip_locked=True, of=BrowserSession))).scalars().all()
        for session in rows:
            try:
                if session.sandbox_id:
                    await OpenSandboxProvider().destroy(session.sandbox_id)
            except Exception:
                # One provider failure must not strand the rest of the batch.
                logger.exception("Browser reaper failed to destroy sandbox; retrying")
                continue
            session.status = "closed"
        await db.commit()
