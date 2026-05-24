# P5: Email Agent + Follow-Up Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Email Agent (reads Gmail via MCP, drafts outreach) and Follow-Up Agent (BullMQ scheduler triggers emails at day 5 and day 12 after application). Both gate on human approval before sending.

**Architecture:** Gmail MCP is called via subprocess (Claude's Gmail MCP server). Email Agent reads inbox threads relevant to a job application, drafts reply or cold outreach. Follow-Up Agent is a BullMQ delayed job scheduled when application status changes to "applied". Resend handles transactional delivery for system emails (not job outreach — that goes via Gmail MCP through user's account).

**Tech Stack:** Gmail MCP (official), Resend, BullMQ delayed jobs, LangChain, ioredis

---

## File Map

| File | Responsibility |
|---|---|
| `backend/app/agents/email_agent.py` | Read Gmail threads, draft reply/outreach with LLM |
| `backend/app/agents/followup_agent.py` | Schedule day-5 and day-12 follow-up jobs |
| `backend/app/services/gmail_service.py` | Gmail MCP client (subprocess wrapper) |
| `backend/app/services/resend_service.py` | Resend client for system transactional emails |
| `backend/app/api/v1/email.py` | Inbox read, compose, send-approval endpoints |
| `backend/tests/unit/test_email_agent.py` | Unit tests — mocked Gmail + LLM |
| `backend/tests/unit/test_followup_agent.py` | Unit tests — mocked queue |
| `worker/src/processors/followup.processor.ts` | BullMQ processor for delayed follow-up jobs |

---

## Task 1: Gmail Service (MCP Client)

**Files:**
- Create: `backend/app/services/gmail_service.py`

- [ ] **Step 1: Implement gmail_service.py**

```python
# backend/app/services/gmail_service.py
"""
Wrapper around the official Gmail MCP server.
Calls MCP tools via the LangChain MCP adapter.
User must have completed Google OAuth and stored refresh token.
"""
from langchain_core.tools import BaseTool
from typing import Any


class GmailMCPClient:
    """Wraps Gmail MCP tools for use in LangGraph agents."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._tools: dict[str, BaseTool] | None = None

    def _get_tools(self) -> dict[str, BaseTool]:
        if self._tools is not None:
            return self._tools
        # Gmail MCP tools loaded from environment-configured MCP server
        # In production: tools registered via LangChain MCP client
        # This factory returns tool stubs that call the MCP server endpoints
        from langchain_community.tools.gmail.search import GmailSearch
        from langchain_community.tools.gmail.get_thread import GmailGetThread
        from langchain_community.tools.gmail.send_message import GmailSendMessage
        from langchain_google_community import GmailToolkit
        toolkit = GmailToolkit()
        self._tools = {tool.name: tool for tool in toolkit.get_tools()}
        return self._tools

    def search_threads(self, query: str, max_results: int = 10) -> list[dict]:
        tools = self._get_tools()
        search_tool = tools.get("search_gmail")
        if not search_tool:
            raise RuntimeError("Gmail search tool not available — check MCP configuration")
        return search_tool.run({"query": query, "max_results": max_results})

    def get_thread(self, thread_id: str) -> dict:
        tools = self._get_tools()
        return tools["get_gmail_thread"].run({"thread_id": thread_id})

    def send_message(self, to: str, subject: str, body: str) -> dict:
        """Sends email. REQUIRES human-in-loop approval before calling."""
        tools = self._get_tools()
        return tools["send_gmail_message"].run({"to": [to], "subject": subject, "message": body})
```

- [ ] **Step 2: Create Resend service**

```python
# backend/app/services/resend_service.py
"""System transactional emails (job alerts, account notifications) via Resend."""
import httpx
from app.core.config import settings


class ResendClient:
    BASE_URL = "https://api.resend.com"

    def __init__(self):
        self._api_key = settings.RESEND_API_KEY

    def send(self, to: str, subject: str, html: str, from_email: str = "noreply@jobagent.ai") -> dict:
        resp = httpx.post(
            f"{self.BASE_URL}/emails",
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json={"from": from_email, "to": [to], "subject": subject, "html": html},
        )
        resp.raise_for_status()
        return resp.json()


resend = ResendClient()
```

- [ ] **Step 3: Add RESEND_API_KEY to config.py**

```python
# backend/app/core/config.py — add field
RESEND_API_KEY: str = ""
```

- [ ] **Step 4: Add to .env.example**

```bash
# .env.example — add
RESEND_API_KEY=re_...
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/gmail_service.py backend/app/services/resend_service.py backend/app/core/config.py .env.example
git commit -m "feat(email): Gmail MCP client and Resend transactional email service"
```

---

## Task 2: Email Agent

**Files:**
- Create: `backend/app/agents/email_agent.py`
- Create: `backend/tests/unit/test_email_agent.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_email_agent.py
import uuid
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage
from app.agents.state import AgentState


def make_state(task: str = "draft_outreach") -> AgentState:
    return AgentState(
        user_id="usr_test123",
        run_id=str(uuid.uuid4()),
        task_type="email",
        messages=[HumanMessage(content="Draft follow-up email for Stripe application")],
        context={
            "task": task,
            "recipient_email": "recruiter@stripe.com",
            "company": "Stripe",
            "role": "Senior Python Engineer",
            "application_id": str(uuid.uuid4()),
        },
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def test_email_agent_drafts_and_pauses_for_approval(mock_llm):
    from app.agents.email_agent import email_agent_node

    mock_llm.responses = [
        "Subject: Following up on Senior Python Engineer application\n\nDear Hiring Team,\n\nI wanted to follow up..."
    ]

    with patch("app.agents.email_agent._get_model_settings", return_value=MagicMock(provider="openai")), \
         patch("app.agents.email_agent._build_llm", return_value=mock_llm), \
         patch("app.agents.email_agent.GmailMCPClient") as mock_gmail_cls:
        mock_gmail = MagicMock()
        mock_gmail.search_threads.return_value = []
        mock_gmail_cls.return_value = mock_gmail
        result = email_agent_node(make_state())

    assert result["status"] == "awaiting_approval"
    assert result["pending_action"]["type"] == "send_email"
    assert "subject" in result["pending_action"]
    assert "body" in result["pending_action"]
    assert result["pending_action"]["recipient"] == "recruiter@stripe.com"


def test_email_agent_never_auto_sends():
    """Email agent must NEVER call gmail.send_message directly."""
    from app.agents.email_agent import email_agent_node

    with patch("app.agents.email_agent._get_model_settings", return_value=MagicMock(provider="openai")), \
         patch("app.agents.email_agent._build_llm", return_value=MagicMock(invoke=MagicMock(return_value=MagicMock(content="Draft email...")))), \
         patch("app.agents.email_agent.GmailMCPClient") as mock_gmail_cls:
        mock_gmail = MagicMock()
        mock_gmail_cls.return_value = mock_gmail
        email_agent_node(make_state())

    mock_gmail.send_message.assert_not_called()
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_email_agent.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement email_agent.py**

```python
# backend/app/agents/email_agent.py
import asyncio
from langchain_core.messages import AIMessage, HumanMessage
from app.agents.state import AgentState
from app.services.gmail_service import GmailMCPClient
from app.core.model_router import _build_llm

OUTREACH_PROMPT = """You are writing a professional follow-up email for a job application.

Company: {company}
Role: {role}
Context from prior threads: {thread_context}

Write a concise, professional email (3-4 short paragraphs max).
Format:
Subject: <subject line>

<email body>

Do NOT include placeholder text like [Your Name]. Write a complete email."""


def _get_model_settings(user_id: str):
    async def _fetch():
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.db import UserModelSettings
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserModelSettings)
                .where(UserModelSettings.user_id == user_id, UserModelSettings.is_active == True)
            )
            return result.scalar_one_or_none()
    return asyncio.get_event_loop().run_until_complete(_fetch())


def email_agent_node(state: AgentState) -> AgentState:
    try:
        user_id = state["user_id"]
        ctx = state["context"]
        company = ctx.get("company", "")
        role = ctx.get("role", "")
        recipient = ctx.get("recipient_email", "")

        model_settings = _get_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings")

        gmail = GmailMCPClient(user_id)
        threads = gmail.search_threads(f"from:{recipient} OR subject:{company}", max_results=3)
        thread_context = "\n".join(str(t) for t in threads[:2]) if threads else "No prior threads."

        llm = _build_llm(model_settings)
        response = llm.invoke([HumanMessage(
            content=OUTREACH_PROMPT.format(company=company, role=role, thread_context=thread_context)
        )])

        full_text = response.content.strip()
        subject = ""
        body = full_text
        if full_text.startswith("Subject:"):
            lines = full_text.split("\n", 2)
            subject = lines[0].replace("Subject:", "").strip()
            body = "\n".join(lines[2:]).strip() if len(lines) > 2 else ""

        # NEVER call gmail.send_message here — human gate required
        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": {
                "type": "send_email",
                "recipient": recipient,
                "subject": subject,
                "body": body,
            },
            "messages": state["messages"] + [AIMessage(content=f"Email draft ready for {recipient}. Review before sending.")],
        }
    except Exception as exc:
        return {**state, "status": "failed", "error": str(exc)}
```

- [ ] **Step 4: Run tests — verify pass**

```bash
pytest tests/unit/test_email_agent.py -v
```

Expected: 2 passed (including the critical `test_email_agent_never_auto_sends`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/email_agent.py backend/tests/unit/test_email_agent.py
git commit -m "feat(agents): Email Agent — Gmail thread context, LLM draft, human-in-loop gate (never auto-sends)"
```

---

## Task 3: Follow-Up Agent + Scheduler

**Files:**
- Create: `backend/app/agents/followup_agent.py`
- Create: `backend/tests/unit/test_followup_agent.py`
- Modify: `worker/src/processors/followup.processor.ts`
- Modify: `worker/src/index.ts`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_followup_agent.py
import uuid
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta


def test_schedule_followups_enqueues_two_jobs():
    from app.agents.followup_agent import schedule_followups

    application_id = str(uuid.uuid4())
    user_id = "usr_test123"

    with patch("app.agents.followup_agent._enqueue_followup") as mock_enqueue:
        schedule_followups(user_id=user_id, application_id=application_id, applied_at=datetime.now(timezone.utc))

    assert mock_enqueue.call_count == 2
    calls = mock_enqueue.call_args_list
    delays = [c.kwargs.get("delay_days") or c.args[2] for c in calls]
    assert 5 in delays
    assert 12 in delays


def test_schedule_followups_does_not_enqueue_if_already_scheduled():
    from app.agents.followup_agent import schedule_followups

    application_id = str(uuid.uuid4())
    with patch("app.agents.followup_agent._enqueue_followup") as mock_enqueue, \
         patch("app.agents.followup_agent._is_already_scheduled", return_value=True):
        schedule_followups(user_id="usr_test", application_id=application_id, applied_at=datetime.now(timezone.utc))

    mock_enqueue.assert_not_called()
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_followup_agent.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement followup_agent.py**

```python
# backend/app/agents/followup_agent.py
import json
import uuid
from datetime import datetime, timezone, timedelta
import redis
from app.core.config import settings

_redis = redis.from_url(settings.REDIS_URL)
FOLLOWUP_QUEUE_KEY = "bull:agent-queue:wait"
SCHEDULED_SET_KEY = "followup:scheduled"


def _is_already_scheduled(application_id: str) -> bool:
    return bool(_redis.sismember(SCHEDULED_SET_KEY, application_id))


def _enqueue_followup(user_id: str, application_id: str, delay_days: int) -> str:
    job_id = str(uuid.uuid4())
    fire_at = datetime.now(timezone.utc) + timedelta(days=delay_days)
    payload = {
        "id": job_id,
        "name": "followup-email",
        "data": {
            "user_id": user_id,
            "application_id": application_id,
            "day": delay_days,
        },
        "opts": {
            "delay": int((fire_at - datetime.now(timezone.utc)).total_seconds() * 1000),
            "attempts": 3,
        },
        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
    }
    _redis.rpush(FOLLOWUP_QUEUE_KEY, json.dumps(payload))
    return job_id


def schedule_followups(user_id: str, application_id: str, applied_at: datetime) -> None:
    if _is_already_scheduled(application_id):
        return
    _enqueue_followup(user_id, application_id, delay_days=5)
    _enqueue_followup(user_id, application_id, delay_days=12)
    _redis.sadd(SCHEDULED_SET_KEY, application_id)
    _redis.expireat(SCHEDULED_SET_KEY, int((applied_at + timedelta(days=30)).timestamp()))
```

- [ ] **Step 4: Create followup BullMQ processor**

```typescript
// worker/src/processors/followup.processor.ts
import { Job } from "bullmq";
import axios from "axios";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000";

export async function processFollowupEmail(job: Job): Promise<void> {
  const { user_id, application_id, day } = job.data;
  await axios.post(
    `${BACKEND_URL}/internal/agents/run-followup`,
    { user_id, application_id, day },
    { headers: { "x-internal-secret": process.env.APP_SECRET_KEY ?? "" } }
  );
}
```

- [ ] **Step 5: Register in worker index.ts**

```typescript
// worker/src/index.ts — add to switch
import { processFollowupEmail } from "./processors/followup.processor";
// in the worker switch:
case "followup-email":
  await processFollowupEmail(job);
  break;
```

- [ ] **Step 6: Run tests — verify pass**

```bash
pytest tests/unit/test_followup_agent.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/followup_agent.py backend/tests/unit/test_followup_agent.py worker/src/processors/followup.processor.ts worker/src/index.ts
git commit -m "feat(agents): Follow-Up Agent — schedule day-5 and day-12 BullMQ delayed jobs, idempotent scheduling"
```

---

## Task 4: Email API

**Files:**
- Create: `backend/app/api/v1/email.py`

- [ ] **Step 1: Implement email.py**

```python
# backend/app/api/v1/email.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.api.v1.deps import get_current_user, get_db
from app.models.db import User, AgentRun, JobApplication
from app.agents.email_agent import email_agent_node
from app.agents.state import AgentState
from app.services.gmail_service import GmailMCPClient
from langchain_core.messages import HumanMessage
from datetime import datetime, timezone
import asyncio

router = APIRouter(prefix="/email", tags=["email"])


class ComposeRequest(BaseModel):
    company: str
    role: str
    recipient_email: str
    application_id: uuid.UUID | None = None


class ApproveEmailRequest(BaseModel):
    run_id: str


@router.post("/compose", response_model=dict)
async def compose_email(
    payload: ComposeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="email",
        status="running",
        input={"company": payload.company, "role": payload.role},
    )
    db.add(agent_run)
    await db.flush()

    state = AgentState(
        user_id=str(current_user.id),
        run_id=run_id,
        task_type="email",
        messages=[HumanMessage(content=f"Draft email for {payload.role} at {payload.company}")],
        context={
            "task": "draft_outreach",
            "company": payload.company,
            "role": payload.role,
            "recipient_email": payload.recipient_email,
        },
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )

    result_state = await asyncio.get_event_loop().run_in_executor(None, email_agent_node, state)

    agent_run.status = result_state["status"]
    if result_state.get("pending_action"):
        agent_run.output = {
            "pending_action": result_state["pending_action"],
        }
    agent_run.completed_at = datetime.now(timezone.utc)

    if result_state["status"] == "failed":
        raise HTTPException(status_code=500, detail=result_state.get("error"))

    return {
        "run_id": run_id,
        "status": result_state["status"],
        "draft": result_state.get("pending_action"),
    }


@router.post("/approve/{run_id}", response_model=dict)
async def approve_and_send_email(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentRun).where(AgentRun.id == uuid.UUID(run_id), AgentRun.user_id == current_user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Run is {run.status}, not awaiting_approval")

    pending = run.output.get("pending_action", {})
    if pending.get("type") != "send_email":
        raise HTTPException(status_code=400, detail="No email pending for this run")

    gmail = GmailMCPClient(str(current_user.id))
    gmail.send_message(
        to=pending["recipient"],
        subject=pending["subject"],
        body=pending["body"],
    )

    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    return {"status": "sent", "recipient": pending["recipient"]}
```

- [ ] **Step 2: Register in main.py**

```python
# backend/app/main.py
from app.api.v1 import users, rag, resume, jobs, email
app.include_router(email.router, prefix="/api/v1")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/email.py backend/app/main.py
git commit -m "feat(api): email compose (draft) and approve-to-send endpoints — human gate enforced"
```

**P5 done. Proceed to P6 (Orchestrator + Frontend).**
