from __future__ import annotations

import logging
import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


def _strip_fences(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1]
        value = value.rsplit("```", 1)[0]
    return value.strip()


def call_llm_json(llm, system_text: str, human_text: str, schema_cls: type[BaseModel]):
    """Invoke an LLM and parse the output into schema_cls.

    Sends [SystemMessage, HumanMessage], parses with
    ``schema_cls.model_validate_json``. On ValidationError retries ONCE with
    the error message appended. Raises the ValidationError if the retry
    also fails. Works with any LLM exposing ``.invoke(messages)`` returning
    an object with ``.content`` (sync path used by LangGraph nodes).
    """
    schema_text = json.dumps(schema_cls.model_json_schema(), separators=(",", ":"))
    system_with_schema = (
        f"{system_text}\n\nJSON_SCHEMA (your output MUST validate against this):\n{schema_text}"
    )
    messages = [SystemMessage(content=system_with_schema), HumanMessage(content=human_text)]
    response = llm.invoke(messages)
    content = response.content if isinstance(response.content, str) else str(response.content)
    try:
        return schema_cls.model_validate_json(_strip_fences(content))
    except ValidationError as exc:
        err_text = str(exc)[:1000]
        logger.warning("LLM JSON parse failed, retrying once: %s", err_text)
        retry_messages = messages + [
            HumanMessage(
                content=(
                    f"Your previous output failed validation: {err_text}. "
                    f"Return ONLY valid JSON matching this schema: {schema_text}"
                )
            )
        ]
        retry_response = llm.invoke(retry_messages)
        retry_content = (
            retry_response.content
            if isinstance(retry_response.content, str)
            else str(retry_response.content)
        )
        return schema_cls.model_validate_json(_strip_fences(retry_content))
