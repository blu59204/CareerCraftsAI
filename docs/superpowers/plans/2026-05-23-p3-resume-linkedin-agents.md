# P3: Resume Agent + LinkedIn Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Resume Agent (RAG retrieval → LLM rewrite → ReportLab PDF) and LinkedIn Agent (RAG retrieval → LLM rewrite → PinchTab profile update). Both are LangGraph nodes that read/write `AgentState`.

**Architecture:** Each agent is a Python function with signature `(state: AgentState) -> AgentState`. Resume Agent retrieves user resume chunks + JD, prompts LLM to rewrite, generates PDF via ReportLab. LinkedIn Agent retrieves profile context, rewrites headline/about/bullets, uses PinchTab MCP to update profile sections. Both pause at human-in-loop gate before any write.

**Tech Stack:** LangGraph 0.2+, LangChain 0.3+, ReportLab 4.x, PinchTab HTTP API, pytest-mock

---

## File Map

| File | Responsibility |
|---|---|
| `backend/app/agents/state.py` | AgentState TypedDict shared across all agents |
| `backend/app/agents/resume_agent.py` | LangGraph node: RAG → LLM rewrite → PDF |
| `backend/app/agents/linkedin_agent.py` | LangGraph node: RAG → LLM rewrite → PinchTab |
| `backend/app/services/pdf_service.py` | ReportLab PDF generation from resume text |
| `backend/app/services/pinchtab_service.py` | HTTP client for PinchTab browser automation |
| `backend/app/api/v1/resume.py` | Resume optimize + download endpoints |
| `backend/tests/unit/test_resume_agent.py` | Unit tests — mocked LLM + RAG |
| `backend/tests/unit/test_pdf_service.py` | Unit tests — PDF bytes output |
| `backend/tests/unit/test_linkedin_agent.py` | Unit tests — mocked LLM + PinchTab |
| `backend/requirements.txt` | Add reportlab |

---

## Task 1: Agent State

**Files:**
- Create: `backend/app/agents/state.py`

- [ ] **Step 1: Implement AgentState**

```python
# backend/app/agents/state.py
from typing import TypedDict, Literal
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/state.py
git commit -m "feat(agents): AgentState TypedDict — shared state contract for all LangGraph nodes"
```

---

## Task 2: PDF Service

**Files:**
- Create: `backend/app/services/pdf_service.py`
- Create: `backend/tests/unit/test_pdf_service.py`

- [ ] **Step 1: Add reportlab to requirements.txt**

```
reportlab==4.1.0
```

```bash
cd backend && source .venv/bin/activate && pip install reportlab==4.1.0
git add backend/requirements.txt && git commit -m "chore(backend): add reportlab for PDF generation"
```

- [ ] **Step 2: Write failing test**

```python
# backend/tests/unit/test_pdf_service.py
import pytest
from app.services.pdf_service import generate_resume_pdf


def test_generate_pdf_returns_bytes():
    resume_text = """John Doe
john@example.com | +1-555-0100

EXPERIENCE
Senior Engineer, Acme Corp (2020-2024)
- Led backend rewrite to FastAPI, cut p99 latency 40%

EDUCATION
B.S. Computer Science, State University (2019)

SKILLS
Python, FastAPI, PostgreSQL, Docker"""
    pdf_bytes = generate_resume_pdf(resume_text, full_name="John Doe")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_pdf_with_empty_text_raises():
    with pytest.raises(ValueError, match="resume_text cannot be empty"):
        generate_resume_pdf("", full_name="Test User")
```

- [ ] **Step 3: Run — verify fails**

```bash
pytest tests/unit/test_pdf_service.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement pdf_service.py**

```python
# backend/app/services/pdf_service.py
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT


def generate_resume_pdf(resume_text: str, full_name: str) -> bytes:
    if not resume_text or not resume_text.strip():
        raise ValueError("resume_text cannot be empty")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    name_style = ParagraphStyle("Name", parent=styles["Heading1"], fontSize=16, spaceAfter=4)
    section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14)

    story = []
    lines = resume_text.strip().split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 4))
        elif stripped.isupper() and len(stripped) < 30:
            story.append(Paragraph(stripped, section_style))
        elif story == [] and stripped:
            story.append(Paragraph(stripped, name_style))
        else:
            safe = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe, body_style))

    doc.build(story)
    return buffer.getvalue()
```

- [ ] **Step 5: Run — verify passes**

```bash
pytest tests/unit/test_pdf_service.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/pdf_service.py backend/tests/unit/test_pdf_service.py
git commit -m "feat(resume): ReportLab PDF generation service with section formatting"
```

---

## Task 3: Resume Agent (LangGraph Node)

**Files:**
- Create: `backend/app/agents/resume_agent.py`
- Create: `backend/tests/unit/test_resume_agent.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_resume_agent.py
import uuid
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from app.agents.state import AgentState


def make_state(jd_text: str = "Python engineer at Stripe") -> AgentState:
    return AgentState(
        user_id="usr_test123",
        run_id=str(uuid.uuid4()),
        task_type="resume_optimize",
        messages=[HumanMessage(content=jd_text)],
        context={"jd_text": jd_text},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def test_resume_agent_calls_rag_and_llm(mock_llm):
    from app.agents.resume_agent import resume_agent_node
    state = make_state()
    mock_chunks = [MagicMock(page_content="5 years Python experience")]

    with patch("app.agents.resume_agent.retrieve", return_value=mock_chunks) as mock_retrieve, \
         patch("app.agents.resume_agent.generate_resume_pdf", return_value=b"%PDF-fake") as mock_pdf, \
         patch("app.agents.resume_agent.get_db_sync") as mock_db_ctx, \
         patch("app.agents.resume_agent.get_model_settings") as mock_ms:
        mock_ms.return_value = MagicMock(provider="anthropic")
        mock_db_ctx.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.return_value.__exit__ = MagicMock(return_value=False)

        with patch("app.agents.resume_agent.get_llm_sync", return_value=mock_llm):
            result_state = resume_agent_node(state)

        mock_retrieve.assert_called_once()
        assert result_state["status"] == "awaiting_approval"
        assert result_state["pending_action"] is not None
        assert result_state["pending_action"]["type"] == "resume_ready"


def test_resume_agent_sets_error_on_exception(mock_llm):
    from app.agents.resume_agent import resume_agent_node
    state = make_state()

    with patch("app.agents.resume_agent.retrieve", side_effect=Exception("pgvector down")), \
         patch("app.agents.resume_agent.get_model_settings", return_value=MagicMock()):
        result_state = resume_agent_node(state)

    assert result_state["status"] == "failed"
    assert "pgvector down" in result_state["error"]
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_resume_agent.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement resume_agent.py**

```python
# backend/app/agents/resume_agent.py
from langchain_core.messages import AIMessage
from app.agents.state import AgentState
from app.services.rag_service import retrieve
from app.services.pdf_service import generate_resume_pdf
from app.core.model_router import get_llm

RESUME_SYSTEM_PROMPT = """You are a professional resume writer using the Google XYZ formula.
Given the candidate's experience (from context) and a job description, rewrite the resume to:
1. Mirror keywords from the JD naturally
2. Quantify achievements where possible
3. Keep bullet points under 2 lines each
4. Use strong action verbs

Return ONLY the resume text — no commentary, no markdown fences."""


def resume_agent_node(state: AgentState) -> AgentState:
    try:
        user_id = state["user_id"]
        jd_text = state["context"].get("jd_text", "")

        from app.core.database import AsyncSessionLocal
        import asyncio

        async def _run():
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                from app.models.db import UserModelSettings
                result = await db.execute(
                    select(UserModelSettings)
                    .where(UserModelSettings.user_id == user_id, UserModelSettings.is_active == True)
                )
                model_settings = result.scalar_one_or_none()
                if not model_settings:
                    raise ValueError("No active model settings for user")
                return model_settings

        model_settings = asyncio.get_event_loop().run_until_complete(_run())

        # Retrieve resume chunks from pgvector
        resume_chunks = retrieve(user_id, "resume", jd_text, model_settings, k=5)
        context_text = "\n\n".join(chunk.page_content for chunk in resume_chunks)

        llm = get_llm.__wrapped__(user_id, None) if hasattr(get_llm, "__wrapped__") else None
        # Use model_settings directly
        from app.core.model_router import _build_llm
        llm = _build_llm(model_settings)

        from langchain_core.messages import SystemMessage, HumanMessage
        messages = [
            SystemMessage(content=RESUME_SYSTEM_PROMPT),
            HumanMessage(content=f"CANDIDATE CONTEXT:\n{context_text}\n\nJOB DESCRIPTION:\n{jd_text}"),
        ]
        response = llm.invoke(messages)
        rewritten_text = response.content

        pdf_bytes = generate_resume_pdf(rewritten_text, full_name="")
        import base64
        pdf_b64 = base64.b64encode(pdf_bytes).decode()

        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": {
                "type": "resume_ready",
                "resume_text": rewritten_text,
                "pdf_b64": pdf_b64,
            },
            "messages": state["messages"] + [AIMessage(content=rewritten_text)],
        }
    except Exception as exc:
        return {**state, "status": "failed", "error": str(exc)}
```

- [ ] **Step 4: Add `_build_llm` helper to model_router.py**

```python
# backend/app/core/model_router.py — add this function at the end of the file

def _build_llm(model_settings) -> BaseChatModel:
    """Build LLM directly from model_settings object (no DB lookup needed)."""
    from app.core.security import decrypt_api_key
    from app.core.config import settings
    api_key = decrypt_api_key(model_settings.api_key_enc, settings.APP_SECRET_KEY)
    match model_settings.provider:
        case "anthropic":
            return ChatAnthropic(model=model_settings.model_name, api_key=api_key)
        case "openai":
            return ChatOpenAI(model=model_settings.model_name, api_key=api_key)
        case "google":
            return ChatGoogleGenerativeAI(model=model_settings.model_name, google_api_key=api_key)
        case "ollama":
            return ChatOllama(model=model_settings.model_name, base_url=model_settings.ollama_url)
        case "nvidia_nim":
            return ChatOpenAI(
                model=model_settings.model_name,
                api_key=api_key,
                base_url="https://integrate.api.nvidia.com/v1",
            )
        case _:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Unknown provider: {model_settings.provider}")
```

- [ ] **Step 5: Run tests — verify pass**

```bash
pytest tests/unit/test_resume_agent.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/resume_agent.py backend/app/core/model_router.py backend/tests/unit/test_resume_agent.py
git commit -m "feat(agents): Resume Agent — RAG retrieval, LLM rewrite, PDF generation with human-in-loop gate"
```

---

## Task 4: PinchTab Service

**Files:**
- Create: `backend/app/services/pinchtab_service.py`

- [ ] **Step 1: Implement pinchtab_service.py**

```python
# backend/app/services/pinchtab_service.py
"""
HTTP client for PinchTab browser automation.
PinchTab docs: https://github.com/pinchtab/pinchtab
"""
import httpx
from app.core.config import settings


class PinchTabClient:
    def __init__(self, session_id: str):
        self._base = settings.PINCHTAB_URL
        self._session = session_id

    def _url(self, path: str) -> str:
        return f"{self._base}/{path}"

    def navigate(self, url: str) -> dict:
        return httpx.post(self._url("navigate"), json={"sessionId": self._session, "url": url}).json()

    def snapshot(self) -> dict:
        return httpx.post(self._url("snapshot"), json={"sessionId": self._session}).json()

    def fill(self, selector: str, value: str) -> dict:
        return httpx.post(self._url("fill"), json={"sessionId": self._session, "selector": selector, "value": value}).json()

    def click(self, selector: str) -> dict:
        return httpx.post(self._url("action"), json={"sessionId": self._session, "action": "click", "selector": selector}).json()

    def close(self) -> None:
        httpx.post(self._url("session/close"), json={"sessionId": self._session})


def new_session(user_id: str) -> PinchTabClient:
    """Create isolated browser session for user."""
    resp = httpx.post(f"{settings.PINCHTAB_URL}/session/new", json={"userId": user_id})
    resp.raise_for_status()
    session_id = resp.json()["sessionId"]
    return PinchTabClient(session_id)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/pinchtab_service.py
git commit -m "feat(browser): PinchTab HTTP client for isolated per-user browser sessions"
```

---

## Task 5: LinkedIn Agent (LangGraph Node)

**Files:**
- Create: `backend/app/agents/linkedin_agent.py`
- Create: `backend/tests/unit/test_linkedin_agent.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_linkedin_agent.py
import uuid
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage
from app.agents.state import AgentState


def make_state() -> AgentState:
    return AgentState(
        user_id="usr_test123",
        run_id=str(uuid.uuid4()),
        task_type="linkedin_optimize",
        messages=[HumanMessage(content="Optimize my LinkedIn profile")],
        context={"target_role": "Senior Python Engineer"},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def test_linkedin_agent_generates_sections_and_pauses(mock_llm):
    from app.agents.linkedin_agent import linkedin_agent_node

    mock_llm.responses = [
        "Dynamic Python engineer | FastAPI | LangChain | 5+ years",  # headline
        "Passionate about building AI-powered backend systems...",    # about
        "• Led migration of monolith to FastAPI microservices\n• Reduced API latency 40%",  # bullets
    ]
    mock_chunks = [MagicMock(page_content="5 years Python, FastAPI, LangChain")]

    with patch("app.agents.linkedin_agent.retrieve", return_value=mock_chunks), \
         patch("app.agents.linkedin_agent._get_model_settings", return_value=MagicMock(provider="openai")), \
         patch("app.agents.linkedin_agent._build_llm", return_value=mock_llm):
        result = linkedin_agent_node(make_state())

    assert result["status"] == "awaiting_approval"
    assert result["pending_action"]["type"] == "linkedin_edits"
    assert "headline" in result["pending_action"]
    assert "about" in result["pending_action"]


def test_linkedin_agent_fails_gracefully():
    from app.agents.linkedin_agent import linkedin_agent_node

    with patch("app.agents.linkedin_agent.retrieve", side_effect=Exception("DB error")), \
         patch("app.agents.linkedin_agent._get_model_settings", return_value=MagicMock()):
        result = linkedin_agent_node(make_state())

    assert result["status"] == "failed"
    assert "DB error" in result["error"]
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_linkedin_agent.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement linkedin_agent.py**

```python
# backend/app/agents/linkedin_agent.py
import asyncio
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from app.agents.state import AgentState
from app.services.rag_service import retrieve
from app.core.model_router import _build_llm

HEADLINE_PROMPT = "Write a LinkedIn headline (max 220 chars) for this candidate targeting: {role}. Context: {context}. Return ONLY the headline text."
ABOUT_PROMPT = "Write a LinkedIn About section (max 2600 chars, 3 paragraphs) for: {role}. Context: {context}. Return ONLY the about text."
BULLETS_PROMPT = "Write 5 LinkedIn experience bullet points using the STAR method for: {role}. Context: {context}. Return ONLY bullets, one per line starting with •."


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


def linkedin_agent_node(state: AgentState) -> AgentState:
    try:
        user_id = state["user_id"]
        target_role = state["context"].get("target_role", "software engineer")

        model_settings = _get_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings")

        chunks = retrieve(user_id, "resume", target_role, model_settings, k=5)
        context_text = "\n".join(c.page_content for c in chunks)

        llm = _build_llm(model_settings)

        headline = llm.invoke([HumanMessage(
            content=HEADLINE_PROMPT.format(role=target_role, context=context_text)
        )]).content

        about = llm.invoke([HumanMessage(
            content=ABOUT_PROMPT.format(role=target_role, context=context_text)
        )]).content

        bullets = llm.invoke([HumanMessage(
            content=BULLETS_PROMPT.format(role=target_role, context=context_text)
        )]).content

        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": {
                "type": "linkedin_edits",
                "headline": headline.strip(),
                "about": about.strip(),
                "experience_bullets": bullets.strip(),
            },
            "messages": state["messages"] + [AIMessage(content=f"LinkedIn sections ready for review.")],
        }
    except Exception as exc:
        return {**state, "status": "failed", "error": str(exc)}
```

- [ ] **Step 4: Run tests — verify pass**

```bash
pytest tests/unit/test_linkedin_agent.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/linkedin_agent.py backend/tests/unit/test_linkedin_agent.py
git commit -m "feat(agents): LinkedIn Agent — RAG retrieval, LLM headline/about/bullets rewrite, human-in-loop gate"
```

---

## Task 6: Resume API Endpoint

**Files:**
- Create: `backend/app/api/v1/resume.py`

- [ ] **Step 1: Implement resume.py**

```python
# backend/app/api/v1/resume.py
import base64
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.api.v1.deps import get_current_user, get_db
from app.models.db import User, UserDocument, AgentRun
from app.agents.resume_agent import resume_agent_node
from app.agents.state import AgentState

router = APIRouter(prefix="/resume", tags=["resume"])


class OptimizeRequest(BaseModel):
    jd_text: str
    resume_document_id: uuid.UUID | None = None


class OptimizeResponse(BaseModel):
    run_id: str
    status: str
    resume_text: str | None = None
    pdf_available: bool = False


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_resume(
    payload: OptimizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="resume",
        status="running",
        input={"jd_text": payload.jd_text[:500]},
    )
    db.add(agent_run)
    await db.flush()

    state = AgentState(
        user_id=str(current_user.id),
        run_id=run_id,
        task_type="resume_optimize",
        messages=[],
        context={"jd_text": payload.jd_text},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )

    import asyncio
    result_state = await asyncio.get_event_loop().run_in_executor(None, resume_agent_node, state)

    agent_run.status = result_state["status"]
    agent_run.completed_at = datetime.now(timezone.utc)
    if result_state.get("pending_action"):
        agent_run.output = {"pending_action": result_state["pending_action"].get("type")}

    if result_state["status"] == "failed":
        raise HTTPException(status_code=500, detail=result_state.get("error", "Agent failed"))

    return OptimizeResponse(
        run_id=run_id,
        status=result_state["status"],
        resume_text=result_state["pending_action"].get("resume_text") if result_state.get("pending_action") else None,
        pdf_available=bool(result_state.get("pending_action", {}).get("pdf_b64")),
    )


@router.get("/download/{run_id}")
async def download_pdf(
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

    if not run.output or "pdf_b64" not in run.output:
        raise HTTPException(status_code=404, detail="PDF not available for this run")

    pdf_bytes = base64.b64decode(run.output["pdf_b64"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=resume_{run_id[:8]}.pdf"},
    )
```

- [ ] **Step 2: Register router in main.py**

```python
# backend/app/main.py — add
from app.api.v1 import users, rag, resume
app.include_router(resume.router, prefix="/api/v1")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/resume.py backend/app/main.py
git commit -m "feat(api): resume optimize and PDF download endpoints"
```

---

## Task 7: Run Full P3 Test Suite

- [ ] **Step 1: Run all unit tests**

```bash
cd backend && source .venv/bin/activate
APP_SECRET_KEY="test-secret-key-32-chars-minimum!!" \
DATABASE_URL="postgresql+asyncpg://x:x@localhost/x" \
SUPABASE_URL="https://x.supabase.co" SUPABASE_SERVICE_KEY="x" \
CLERK_SECRET_KEY="sk_test_x" REDIS_URL="redis://localhost:6379" \
pytest tests/unit -v
```

Expected: All tests pass (config, security, model_router, rag_service, pdf_service, resume_agent, linkedin_agent).

- [ ] **Step 2: Commit**

```bash
git commit -m "chore(p3): Phase 3 complete — Resume Agent + LinkedIn Agent with tests"
```

**P3 done. Proceed to P4 (Job Search + BullMQ).**
