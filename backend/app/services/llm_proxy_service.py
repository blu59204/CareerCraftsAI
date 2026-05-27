"""
llm_proxy_service.py — Output filter to redact API keys from LLM responses.

Prevents prompt injection attacks from extracting API keys by scanning all
LLM output for known key patterns and replacing them with [REDACTED].

Integrates as a LangChain callback handler attached to every LLM call.
"""
import re
import logging
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

# Patterns that match known API key formats
_KEY_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),          # OpenAI
    re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"),      # Anthropic
    re.compile(r"AIza[a-zA-Z0-9_-]{30,}"),          # Google
    re.compile(r"gsk_[a-zA-Z0-9_-]{20,}"),          # Groq
    re.compile(r"nvapi-[a-zA-Z0-9_-]{20,}"),        # NVIDIA NIM
    re.compile(r"hf_[a-zA-Z0-9]{20,}"),             # HuggingFace
    re.compile(r"xai-[a-zA-Z0-9_-]{20,}"),          # xAI
    re.compile(r"Bearer\s+[a-zA-Z0-9_.-]{20,}"),    # Generic bearer tokens
    re.compile(r"[a-f0-9]{32,64}"),                 # Hex keys (32+ chars)
]

REDACTED = "[REDACTED]"


def redact_keys(text: str) -> str:
    """Scan text for API key patterns and replace with [REDACTED].

    Args:
        text: Raw LLM output text

    Returns:
        Sanitized text with any detected keys redacted
    """
    if not text:
        return text

    result = text
    for pattern in _KEY_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return result


class KeyRedactionCallback(BaseCallbackHandler):
    """LangChain callback that redacts API keys from LLM output.

    Attach to any LLM call to ensure keys never leak through prompt injection.

    Usage:
        llm = ChatOpenAI(..., callbacks=[KeyRedactionCallback()])
    """

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Redact keys from all generations in the response."""
        for generations in response.generations:
            for gen in generations:
                if gen.text:
                    original = gen.text
                    gen.text = redact_keys(gen.text)
                    if gen.text != original:
                        logger.warning("Redacted potential API key from LLM output")
                if hasattr(gen, "message") and gen.message and gen.message.content:
                    original = gen.message.content
                    gen.message.content = redact_keys(gen.message.content)


def get_redaction_callback() -> KeyRedactionCallback:
    """Get a singleton redaction callback instance."""
    return KeyRedactionCallback()
