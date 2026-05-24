"""
memory/embedder.py — Routes embedding requests to the user's configured provider.

Falls back to nomic-embed-text via Ollama if the primary provider fails.
Uses Redis to cache embeddings for 1 hour to minimise duplicate API calls.
"""

import hashlib
import json
import logging
from typing import Optional

import redis

logger = logging.getLogger(__name__)

# Target dimensionality for pgvector column (vector(1536))
_DIMS = 1536


class MemoryEmbedder:
    """
    Embed text using the user's active LLM provider.

    Supported providers: openai, google, nvidia_nim, ollama, anthropic.
    Anthropic does not expose an embeddings API so it routes to the Ollama fallback.
    """

    def __init__(
        self,
        user_settings: dict,
        redis_client: Optional[redis.Redis] = None,
    ) -> None:
        self.provider: str = user_settings.get("provider", "openai")
        self.api_key: str = user_settings.get("api_key", "")
        self.redis = redis_client
        self.DIMS = _DIMS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        """
        Embed a single text string.

        Checks Redis cache first; stores result for 1 hour on success.
        If all providers fail, returns a zero vector so callers can still
        save the memory row with NULL embedding.
        """
        cache_key = self._cache_key(text)

        if self.redis:
            try:
                cached = self.redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.debug(f"Redis cache read failed: {e}")

        try:
            vec = await self._embed_with_provider(text)
        except Exception as e:
            logger.warning(
                f"Primary embedding failed (provider={self.provider}): {e}. "
                "Trying Ollama nomic-embed-text fallback."
            )
            try:
                vec = await self._ollama_embed(text)
            except Exception as e2:
                logger.error(
                    f"All embedding providers failed: {e2}. Returning zero vector."
                )
                return [0.0] * self.DIMS

        vec = self._pad_to_dims(vec)

        if self.redis:
            try:
                self.redis.setex(cache_key, 3600, json.dumps(vec))
            except Exception as e:
                logger.debug(f"Redis cache write failed: {e}")

        return vec

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts concurrently."""
        import asyncio

        return await asyncio.gather(*[self.embed(t) for t in texts])

    # ------------------------------------------------------------------
    # Internal routing
    # ------------------------------------------------------------------

    async def _embed_with_provider(self, text: str) -> list[float]:
        if self.provider == "openai":
            return await self._openai_embed(text)
        elif self.provider == "google":
            return await self._google_embed(text)
        elif self.provider == "nvidia_nim":
            return await self._nvidia_embed(text)
        else:
            # anthropic, ollama, unknown — all use Ollama
            return await self._ollama_embed(text)

    async def _openai_embed(self, text: str) -> list[float]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        resp = await client.embeddings.create(
            model="text-embedding-3-small", input=text
        )
        return resp.data[0].embedding

    async def _google_embed(self, text: str) -> list[float]:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        result = genai.embed_content(model="models/embedding-001", content=text)
        return result["embedding"]

    async def _ollama_embed(self, text: str) -> list[float]:
        import ollama

        resp = await ollama.AsyncClient().embeddings(
            model="nomic-embed-text", prompt=text
        )
        return resp["embedding"]

    async def _nvidia_embed(self, text: str) -> list[float]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://integrate.api.nvidia.com/v1",
        )
        resp = await client.embeddings.create(
            model="nvidia/nv-embedqa-e5-v5", input=text
        )
        return resp.data[0].embedding

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode()).hexdigest()
        return f"emb:{digest}"

    def _pad_to_dims(self, vec: list[float]) -> list[float]:
        """Truncate or zero-pad vector to self.DIMS dimensions."""
        if len(vec) >= self.DIMS:
            return vec[: self.DIMS]
        return vec + [0.0] * (self.DIMS - len(vec))
