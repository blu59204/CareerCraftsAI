"""
memory/tests/test_embedder.py — MemoryEmbedder provider routing.

Covers the google.generativeai path specifically: that SDK is synchronous,
so _google_embed must run it via asyncio.to_thread rather than calling it
directly on the event loop.
"""

from __future__ import annotations

import sys
import types

import pytest

from memory.embedder import MemoryEmbedder


@pytest.mark.asyncio
async def test_google_embed_offloads_the_blocking_sdk_call(monkeypatch):
    calls: list[str] = []

    def fake_configure(api_key: str) -> None:
        calls.append("configure")

    def fake_embed_content(model: str, content: str, output_dimensionality: int) -> dict:
        calls.append("embed_content")
        assert model == "models/gemini-embedding-001"
        assert output_dimensionality == 768
        return {"embedding": [0.1, 0.2, 0.3]}

    fake_genai = types.SimpleNamespace(configure=fake_configure, embed_content=fake_embed_content)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

    embedder = MemoryEmbedder({"provider": "google", "api_key": "test-key"})
    result = await embedder._google_embed("hello world")

    assert result == [0.1, 0.2, 0.3]
    assert calls == ["configure", "embed_content"]
