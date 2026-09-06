"""
interview_coach_agent_v2.py — Interactive mock interview agent.

Generates role-specific questions, evaluates answers on 3 dimensions
(clarity, relevance, depth 0-10 each), and tracks session state in Redis.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState

SCORING_PROMPT = """Score this interview answer on 3 dimensions (0-10 each). Return JSON only.
Question: {question}
Answer: {answer}
Return: {{"clarity": N, "relevance": N, "depth": N, "feedback": "2-3 sentences of specific feedback"}}"""


class InterviewCoachAgent(BaseAgent):
    async def run(self, state: AgentState) -> AgentState:
        ctx = state["context"]
        session_id = ctx.get("session_id")
        answer = ctx.get("answer")

        if not session_id:
            return await self._start_session(state)

        session_data = await self._get_session(session_id)
        if not session_data:
            state["status"] = "failed"
            state["error"] = "Session expired or not found"
            return state

        if not answer:
            q = session_data["questions"][0]
            state["result"] = {"question": q, "session_id": session_id, "question_number": 1}
            state["status"] = "completed"
            return state

        llm = await self._get_llm(state["user_id"])
        current_q = session_data["questions"][session_data["current_index"]]
        resp = await llm.ainvoke([{"role": "user", "content": SCORING_PROMPT.format(
            question=current_q, answer=answer,
        )}])

        try:
            raw = resp.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            scores = json.loads(raw)
        except json.JSONDecodeError:
            scores = {"clarity": 5, "relevance": 5, "depth": 5, "feedback": "Could not evaluate this answer."}

        session_data["answers"].append(answer)
        session_data["scores"].append(scores)
        session_data["current_index"] += 1

        session_complete = session_data["current_index"] >= len(session_data["questions"])

        if session_complete:
            avg_clarity = sum(s["clarity"] for s in session_data["scores"]) / len(session_data["scores"])
            avg_relevance = sum(s["relevance"] for s in session_data["scores"]) / len(session_data["scores"])
            avg_depth = sum(s["depth"] for s in session_data["scores"]) / len(session_data["scores"])
            overall = round((avg_clarity + avg_relevance + avg_depth) / 3)

            from app.core.sync_db import _get_sync_factory
            from app.models.db import InterviewSession
            factory = _get_sync_factory()
            with factory() as db:
                session = InterviewSession(
                    id=uuid.UUID(session_id),
                    user_id=uuid.UUID(state["user_id"]),
                    role=session_data["role"],
                    company=session_data.get("company"),
                    questions=session_data["questions"],
                    answers=session_data["answers"],
                    scores=session_data["scores"],
                    overall_score=overall,
                    summary={"avg_clarity": avg_clarity, "avg_relevance": avg_relevance, "avg_depth": avg_depth},
                    status="completed",
                    completed_at=datetime.now(timezone.utc),
                )
                db.add(session)
                db.commit()

            await self.redis.delete(f"interview:{session_id}")
            state["result"] = {
                "scores": scores,
                "feedback": scores["feedback"],
                "session_complete": True,
                "summary": {"avg_clarity": round(avg_clarity, 1), "avg_relevance": round(avg_relevance, 1), "avg_depth": round(avg_depth, 1), "overall": overall},
            }
        else:
            next_q = session_data["questions"][session_data["current_index"]]
            await self.redis.setex(f"interview:{session_id}", 7200, json.dumps(session_data))
            state["result"] = {
                "scores": scores,
                "feedback": scores["feedback"],
                "next_question": next_q,
                "session_complete": False,
                "question_number": session_data["current_index"] + 1,
            }

        state["status"] = "completed"
        return state

    async def _start_session(self, state: AgentState) -> AgentState:
        ctx = state["context"]
        role = ctx.get("role", "Software Engineer")
        company = ctx.get("company", "")
        interview_type = ctx.get("interview_type", "mixed")
        num_questions = ctx.get("num_questions", 5)

        llm = await self._get_llm(state["user_id"])
        resp = await llm.ainvoke([{"role": "user", "content": (
            f"Generate {num_questions} {interview_type} interview questions for a {role} role"
            f"{' at ' + company if company else ''}. Return JSON array of strings only."
        )}])

        try:
            raw = resp.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
            questions = json.loads(raw)
        except json.JSONDecodeError:
            questions = [f"Tell me about your experience as a {role}."]

        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": state["user_id"],
            "role": role,
            "company": company,
            "questions": questions,
            "answers": [],
            "scores": [],
            "current_index": 0,
        }
        await self.redis.setex(f"interview:{session_id}", 7200, json.dumps(session_data))

        state["result"] = {"session_id": session_id, "first_question": questions[0], "total_questions": len(questions)}
        state["status"] = "completed"
        return state

    async def _get_session(self, session_id: str) -> dict | None:
        raw = await self.redis.get(f"interview:{session_id}")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None


def interview_coach_agent_node_v2(state: AgentState) -> AgentState:
    import redis.asyncio as aioredis
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
            try:
                agent = InterviewCoachAgent(db, redis)
                await agent.set_run_id(state["run_id"])
                return await agent.run(state)
            finally:
                await redis.aclose()
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run()).result()
