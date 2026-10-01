"""Bounded public HTTPS fetches with DNS pinning and per-hop SSRF validation."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

import httpx


async def public_get(
    url: str, *, headers: dict | None = None, max_bytes=4_000_000, json_body: dict | None = None
):
    for _ in range(4):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise ValueError("Only public HTTPS on port 443 is allowed")
        addresses = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(
                parsed.hostname,
                443,
                type=socket.SOCK_STREAM,
            ),
            3,
        )
        ips = {item[4][0] for item in addresses}
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise ValueError("Host must resolve only to public addresses")
        original = httpx.URL(url)
        pinned = original.copy_with(
            host=sorted(ips, key=lambda ip: (ipaddress.ip_address(ip).version, ip))[0]
        )
        request_headers = {
            **(headers or {}),
            "Host": parsed.hostname,
            "User-Agent": "CareerCraftJobDiscovery/1.0",
        }
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
            async with client.stream(
                "GET" if json_body is None else "POST",
                pinned,
                headers=request_headers,
                json=json_body,
                extensions={"sni_hostname": parsed.hostname.encode()},
            ) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    if json_body is not None:
                        raise ValueError("A POST is never redirected")
                    next_url = original.join(response.headers["location"])
                    if next_url.host != original.host:
                        headers = {
                            k: v
                            for k, v in (headers or {}).items()
                            if k.lower() not in {"authorization", "cookie"}
                        }
                    url = str(next_url)
                    continue
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > max_bytes:
                        raise ValueError("Response exceeds size limit")
                return httpx.Response(
                    response.status_code,
                    headers={
                        k: v
                        for k, v in response.headers.items()
                        if k.lower() not in {"content-encoding", "content-length"}
                    },
                    content=bytes(content),
                    request=httpx.Request("GET", original),
                )
    raise ValueError("Too many redirects")
