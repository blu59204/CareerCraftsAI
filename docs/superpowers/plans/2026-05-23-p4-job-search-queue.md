# P4: Job Search Agent + BullMQ Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Job Search Agent (PinchTab browses LinkedIn, LLM scores matches) and BullMQ Node.js worker for async job queue processing. Jobs submitted to queue; worker runs agent in background; results stored in `job_applications` table.

**Architecture:** `POST /api/v1/jobs/search` enqueues a BullMQ job via Redis. Node.js worker picks up job, calls FastAPI internal endpoint to run Job Search Agent. Agent uses PinchTab to navigate LinkedIn, snapshots job listings, LLM scores each against user profile, returns top N matches. Results written to `job_applications` table. Frontend polls `/api/v1/jobs/results/{queue_job_id}` or uses SSE stream.

**Tech Stack:** BullMQ 5, Redis 7, Node.js 20, TypeScript, PinchTab HTTP API, ioredis

---

## File Map

| File | Responsibility |
|---|---|
| `backend/app/agents/job_search.py` | LangGraph node: PinchTab navigate → snapshot → LLM score |
| `backend/app/api/v1/jobs.py` | Search trigger, results, application CRUD |
| `backend/tests/unit/test_job_search_agent.py` | Unit tests — mocked PinchTab + LLM |
| `worker/package.json` | BullMQ worker deps |
| `worker/tsconfig.json` | TypeScript config |
| `worker/src/index.ts` | Worker entrypoint |
| `worker/src/queues/agent-queue.ts` | Queue definition |
| `worker/src/processors/job-search.processor.ts` | Job search processor |
| `worker/Dockerfile` | Worker container |

---

## Task 1: Job Search Agent

**Files:**
- Create: `backend/app/agents/job_search.py`
- Create: `backend/tests/unit/test_job_search_agent.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_job_search_agent.py
import uuid
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage
from app.agents.state import AgentState

MOCK_SNAPSHOT = {
    "jobs": [
        {"title": "Senior Python Engineer", "company": "Stripe", "url": "https://stripe.com/jobs/1", "description": "FastAPI, PostgreSQL, 5+ years"},
        {"title": "Backend Engineer", "company": "Acme", "url": "https://acme.com/jobs/2", "description": "Django, Redis, 3+ years"},
    ]
}


def make_state(search_query: str = "Python engineer remote") -> AgentState:
    return AgentState(
        user_id="usr_test123",
        run_id=str(uuid.uuid4()),
        task_type="job_search",
        messages=[HumanMessage(content=search_query)],
        context={"search_query": search_query, "location": "Remote", "max_results": 10},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def test_job_search_agent_navigates_and_scores(mock_llm):
    from app.agents.job_search import job_search_agent_node

    mock_llm.responses = ["85", "62"]  # match scores
    mock_pinchtab = MagicMock()
    mock_pinchtab.navigate.return_value = {"ok": True}
    mock_pinchtab.snapshot.return_value = MOCK_SNAPSHOT

    with patch("app.agents.job_search.new_session", return_value=mock_pinchtab), \
         patch("app.agents.job_search._get_model_settings", return_value=MagicMock(provider="openai")), \
         patch("app.agents.job_search._build_llm", return_value=mock_llm), \
         patch("app.agents.job_search._get_user_profile", return_value="Python engineer 5 years FastAPI"):
        result = job_search_agent_node(make_state())

    assert result["status"] == "completed"
    assert result["result"] is not None
    assert "matches" in result["result"]
    assert len(result["result"]["matches"]) == 2
    mock_pinchtab.close.assert_called_once()


def test_job_search_agent_closes_session_on_error():
    from app.agents.job_search import job_search_agent_node

    mock_pinchtab = MagicMock()
    mock_pinchtab.navigate.side_effect = Exception("PinchTab connection refused")

    with patch("app.agents.job_search.new_session", return_value=mock_pinchtab), \
         patch("app.agents.job_search._get_model_settings", return_value=MagicMock()):
        result = job_search_agent_node(make_state())

    assert result["status"] == "failed"
    mock_pinchtab.close.assert_called_once()  # session must close even on error
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_job_search_agent.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement job_search.py**

```python
# backend/app/agents/job_search.py
import asyncio
import time
from langchain_core.messages import AIMessage, HumanMessage
from app.agents.state import AgentState
from app.services.pinchtab_service import new_session
from app.core.model_router import _build_llm

LINKEDIN_JOBS_URL = "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}&f_TPR=r86400"

SCORE_PROMPT = """Rate how well this job matches the candidate profile. Return ONLY a number 0-100.

Candidate profile:
{profile}

Job: {title} at {company}
Description: {description}

Score (0-100):"""


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


def _get_user_profile(user_id: str) -> str:
    """Get user's primary resume text for scoring context."""
    async def _fetch():
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.db import UserDocument
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserDocument)
                .where(UserDocument.user_id == user_id, UserDocument.doc_type == "resume", UserDocument.is_primary == True)
            )
            doc = result.scalar_one_or_none()
            return doc.raw_text[:2000] if doc and doc.raw_text else ""
    return asyncio.get_event_loop().run_until_complete(_fetch())


def job_search_agent_node(state: AgentState) -> AgentState:
    session = None
    try:
        user_id = state["user_id"]
        ctx = state["context"]
        query = ctx.get("search_query", "software engineer")
        location = ctx.get("location", "Remote")
        max_results = min(ctx.get("max_results", 10), 25)

        model_settings = _get_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings")

        user_profile = _get_user_profile(user_id)
        llm = _build_llm(model_settings)
        session = new_session(user_id)

        url = LINKEDIN_JOBS_URL.format(
            query=query.replace(" ", "%20"),
            location=location.replace(" ", "%20"),
        )
        session.navigate(url)
        time.sleep(2)  # allow page render
        snapshot_data = session.snapshot()

        jobs = snapshot_data.get("jobs", [])[:max_results]
        scored = []
        for job in jobs:
            try:
                score_response = llm.invoke([HumanMessage(
                    content=SCORE_PROMPT.format(
                        profile=user_profile,
                        title=job.get("title", ""),
                        company=job.get("company", ""),
                        description=job.get("description", "")[:500],
                    )
                )])
                score = int("".join(filter(str.isdigit, score_response.content.strip()[:3])) or "0")
            except Exception:
                score = 0
            scored.append({**job, "match_score": score})

        scored.sort(key=lambda j: j["match_score"], reverse=True)

        return {
            **state,
            "status": "completed",
            "result": {"matches": scored, "total_found": len(jobs)},
            "messages": state["messages"] + [
                AIMessage(content=f"Found {len(scored)} jobs. Top match: {scored[0]['title']} at {scored[0]['company']} ({scored[0]['match_score']}%) " if scored else "No jobs found.")
            ],
        }
    except Exception as exc:
        return {**state, "status": "failed", "error": str(exc)}
    finally:
        if session:
            session.close()
```

- [ ] **Step 4: Run tests — verify pass**

```bash
pytest tests/unit/test_job_search_agent.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/job_search.py backend/tests/unit/test_job_search_agent.py
git commit -m "feat(agents): Job Search Agent — PinchTab LinkedIn navigation, LLM match scoring, session cleanup"
```

---

## Task 2: Jobs API Endpoint

**Files:**
- Create: `backend/app/api/v1/jobs.py`

- [ ] **Step 1: Implement jobs.py**

```python
# backend/app/api/v1/jobs.py
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.api.v1.deps import get_current_user, get_db
from app.models.db import User, JobApplication, AgentRun
from app.services.queue_service import enqueue_job_search

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobSearchRequest(BaseModel):
    search_query: str
    location: str = "Remote"
    max_results: int = 10


class JobSearchResponse(BaseModel):
    queue_job_id: str
    status: str = "queued"


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    company: str
    role: str
    match_score: int | None
    status: str
    applied_at: datetime | None

    model_config = {"from_attributes": True}


@router.post("/search", response_model=JobSearchResponse)
async def search_jobs(
    payload: JobSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.max_results > 25:
        raise HTTPException(status_code=400, detail="max_results cannot exceed 25")

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="job_search",
        status="running",
        input={"search_query": payload.search_query, "location": payload.location},
    )
    db.add(agent_run)
    await db.flush()

    queue_job_id = await enqueue_job_search(
        user_id=str(current_user.id),
        run_id=run_id,
        search_query=payload.search_query,
        location=payload.location,
        max_results=payload.max_results,
    )
    return JobSearchResponse(queue_job_id=queue_job_id)


@router.get("/applications", response_model=list[ApplicationResponse])
async def list_applications(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(JobApplication).where(JobApplication.user_id == current_user.id)
    if status:
        query = query.where(JobApplication.status == status)
    result = await db.execute(query.order_by(JobApplication.applied_at.desc()))
    return result.scalars().all()


@router.patch("/applications/{application_id}/status", response_model=ApplicationResponse)
async def update_application_status(
    application_id: uuid.UUID,
    status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    valid = {"saved", "applied", "viewed", "interview", "offer", "rejected"}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"status must be one of: {valid}")

    result = await db.execute(
        select(JobApplication)
        .where(JobApplication.id == application_id, JobApplication.user_id == current_user.id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app.status = status
    if status == "applied":
        app.applied_at = datetime.now(timezone.utc)
    return app
```

- [ ] **Step 2: Create queue_service.py**

```python
# backend/app/services/queue_service.py
import json
import uuid
import redis
from app.core.config import settings

_redis = redis.from_url(settings.REDIS_URL)
QUEUE_KEY = "bull:agent-queue:wait"


async def enqueue_job_search(
    user_id: str, run_id: str, search_query: str, location: str, max_results: int
) -> str:
    job_id = str(uuid.uuid4())
    payload = {
        "id": job_id,
        "name": "job-search",
        "data": {
            "user_id": user_id,
            "run_id": run_id,
            "search_query": search_query,
            "location": location,
            "max_results": max_results,
        },
        "opts": {"attempts": 3, "backoff": {"type": "exponential", "delay": 5000}},
        "timestamp": int(__import__("time").time() * 1000),
    }
    _redis.rpush(QUEUE_KEY, json.dumps(payload))
    return job_id
```

- [ ] **Step 3: Register router in main.py**

```python
# backend/app/main.py — add
from app.api.v1 import users, rag, resume, jobs
app.include_router(jobs.router, prefix="/api/v1")
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/jobs.py backend/app/services/queue_service.py backend/app/main.py
git commit -m "feat(api): job search and applications endpoints with BullMQ queue enqueue"
```

---

## Task 3: BullMQ Worker (Node.js)

**Files:**
- Create: `worker/package.json`
- Create: `worker/tsconfig.json`
- Create: `worker/src/index.ts`
- Create: `worker/src/queues/agent-queue.ts`
- Create: `worker/src/processors/job-search.processor.ts`
- Create: `worker/Dockerfile`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "jobagent-worker",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "ts-node src/index.ts"
  },
  "dependencies": {
    "bullmq": "^5.4.0",
    "ioredis": "^5.3.2",
    "axios": "^1.6.8"
  },
  "devDependencies": {
    "@types/node": "^20.12.7",
    "ts-node": "^10.9.2",
    "typescript": "^5.4.5"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  }
}
```

- [ ] **Step 3: Create agent-queue.ts**

```typescript
// worker/src/queues/agent-queue.ts
import { Queue } from "bullmq";
import { connection } from "../index";

export const agentQueue = new Queue("agent-queue", { connection });
```

- [ ] **Step 4: Create job-search.processor.ts**

```typescript
// worker/src/processors/job-search.processor.ts
import { Job } from "bullmq";
import axios from "axios";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000";

export async function processJobSearch(job: Job): Promise<void> {
  const { user_id, run_id, search_query, location, max_results } = job.data;

  try {
    await axios.post(`${BACKEND_URL}/internal/agents/run-job-search`, {
      user_id,
      run_id,
      search_query,
      location,
      max_results,
    });
  } catch (err: any) {
    const message = err?.response?.data?.detail ?? err.message;
    throw new Error(`Job search failed for run ${run_id}: ${message}`);
  }
}
```

- [ ] **Step 5: Create worker index.ts**

```typescript
// worker/src/index.ts
import { Worker, ConnectionOptions } from "bullmq";
import { processJobSearch } from "./processors/job-search.processor";

const REDIS_URL = process.env.REDIS_URL ?? "redis://redis:6379";
const url = new URL(REDIS_URL);

export const connection: ConnectionOptions = {
  host: url.hostname,
  port: parseInt(url.port ?? "6379"),
  password: url.password || undefined,
};

const worker = new Worker(
  "agent-queue",
  async (job) => {
    switch (job.name) {
      case "job-search":
        await processJobSearch(job);
        break;
      default:
        throw new Error(`Unknown job type: ${job.name}`);
    }
  },
  {
    connection,
    concurrency: 2,  // max 2 concurrent jobs per worker instance
    limiter: { max: 10, duration: 60_000 },  // 10 jobs/min global
  }
);

worker.on("completed", (job) => console.log(`[worker] job ${job.id} (${job.name}) completed`));
worker.on("failed", (job, err) => console.error(`[worker] job ${job?.id} failed:`, err.message));

console.log("[worker] BullMQ worker started, listening on agent-queue");
```

- [ ] **Step 6: Create worker Dockerfile**

```dockerfile
# worker/Dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
CMD ["node", "dist/index.js"]
```

- [ ] **Step 7: Install worker deps and build**

```bash
cd worker && npm install && npm run build
```

Expected: `dist/index.js` created, no TypeScript errors.

- [ ] **Step 8: Commit**

```bash
cd ..
git add worker/
git commit -m "feat(worker): BullMQ Node.js worker with job-search processor, concurrency=2, rate limit 10/min"
```

---

## Task 4: Internal Agent Trigger Endpoint

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/app/api/internal.py`

- [ ] **Step 1: Create internal.py**

```python
# backend/app/api/internal.py
"""
Internal endpoints called by the BullMQ worker — not exposed via Nginx.
Protected by shared internal secret, not Clerk JWT.
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from app.core.config import settings

router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_internal(x_internal_secret: str = Header(...)):
    if x_internal_secret != settings.APP_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


class JobSearchTrigger(BaseModel):
    user_id: str
    run_id: str
    search_query: str
    location: str
    max_results: int


@router.post("/agents/run-job-search", dependencies=[])
async def run_job_search(
    payload: JobSearchTrigger,
    x_internal_secret: str = Header(...),
):
    _verify_internal(x_internal_secret)

    from app.agents.job_search import job_search_agent_node
    from app.agents.state import AgentState
    from langchain_core.messages import HumanMessage
    import asyncio
    from datetime import datetime, timezone
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.db import AgentRun
    import uuid

    state = AgentState(
        user_id=payload.user_id,
        run_id=payload.run_id,
        task_type="job_search",
        messages=[HumanMessage(content=payload.search_query)],
        context={
            "search_query": payload.search_query,
            "location": payload.location,
            "max_results": payload.max_results,
        },
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )

    result_state = await asyncio.get_event_loop().run_in_executor(None, job_search_agent_node, state)

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AgentRun).where(AgentRun.id == uuid.UUID(payload.run_id)))
        run = res.scalar_one_or_none()
        if run:
            run.status = result_state["status"]
            run.output = result_state.get("result")
            run.completed_at = datetime.now(timezone.utc)
        await db.commit()

    return {"status": result_state["status"]}
```

- [ ] **Step 2: Register in main.py**

```python
# backend/app/main.py — add
from app.api import internal
app.include_router(internal.router)
```

- [ ] **Step 3: Update worker to send internal secret header**

```typescript
// worker/src/processors/job-search.processor.ts — update axios call
await axios.post(`${BACKEND_URL}/internal/agents/run-job-search`, {
  user_id, run_id, search_query, location, max_results,
}, {
  headers: { "x-internal-secret": process.env.APP_SECRET_KEY ?? "" }
});
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/internal.py backend/app/main.py worker/src/processors/job-search.processor.ts
git commit -m "feat(internal): internal trigger endpoint for worker→agent communication, protected by shared secret"
```

**P4 done. Proceed to P5 (Email + Follow-Up Agents).**
