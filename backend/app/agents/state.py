from typing import Literal, TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    user_id: str
    run_id: str
    task_type: str
    messages: list[BaseMessage]
    context: dict                   # RAG chunks, JD text, etc.
    status: Literal["running", "awaiting_approval", "completed", "failed"]
    pending_action: dict | None     # populated at human-in-loop checkpoints
    result: dict | None
    error: str | None
