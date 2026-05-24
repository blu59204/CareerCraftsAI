"""
harness.py — AgentHarness wraps the LangGraph orchestrator with:

  1. Memory-based context injection (pre-run)
  2. Episode saving (post-run)
  3. Adaptive strategy selection based on past outcomes
  4. Reflection loop that improves agent prompts over time

Usage::

    harness = AgentHarness(db_url=settings.DATABASE_URL, redis_url=settings.REDIS_URL)
    result = await harness.run(
        user_id=user_id,
        task_type="resume_optimize",
        context={"jd_text": "...", "resume_text": "..."},
        user_settings={"provider": "openai", "api_key": "..."},
    )

Graceful degradation
--------------------
If the memory system is unavailable (DB/Redis errors), the orchestrator is
invoked without context injection.  Errors are logged but never re-raised.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Awaitable
from datetime import UTC, datetime, timedelta
from typing import Any

from langchain_core.messages import HumanMessage

from app.agents.orchestrator import orchestrator
from app.agents.state import AgentState
from app.agents.strategies import TASK_TO_AGENT, strategies_for_task
from app.agents.memory import MemoryManager

logger = logging.getLogger(__name__)

# How many new episodes trigger an early reflection (before 24-h timer fires)
_REFLECTION_EPISODE_THRESHOLD = 20
# TTL for reflection timestamp stored in Redis (seconds) — 25 h so it ages out
_REFLECTION_REDIS_TTL = 90_000

# ──────────────────────────────────────────────────────────────────────────────
# Reflection-hook type
# ──────────────────────────────────────────────────────────────────────────────
ReflectionHook = Callable[[str, list[dict[str, Any]]], Awaitable[None]]


class AgentHarness:
    """
    Wraps the LangGraph orchestrator with memory-driven context injection,
    episode tracking, and adaptive strategy selection.

    The harness evolves over time: it observes which strategies produce
    successful outcomes and biases future runs toward those strategies.
    """

    def __init__(self, db_url: str, redis_url: str) -> None:
        self._memory = MemoryManager(db_url=db_url, redis_url=redis_url)
        self._initialized = False
        self._reflection_hooks: list[ReflectionHook] = []
        self._init_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    async def _ensure_initialized(self) -> None:
        """Lazy initialisation — safe to call from multiple coroutines."""
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            await self._memory.initialize()
            self._initialized = True

    async def close(self) -> None:
        """Release DB pool and Redis connections."""
        await self._memory.close()

    # ------------------------------------------------------------------
    # External hook registration
    # ------------------------------------------------------------------

    def add_reflection_hook(self, hook: ReflectionHook) -> None:
        """
        Register a callback that is invoked after every episode save.

        The hook receives (agent_type, [episode_dict, ...]) and can perform
        custom post-processing (e.g. push metrics, send webhooks).
        """
        self._reflection_hooks.append(hook)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        user_id: str,
        task_type: str,
        context: dict[str, Any],
        user_settings: dict[str, Any],
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Main entry point.

        Steps
        -----
        1. build_agent_context() from memory (preferences, blacklist, learnings,
           past episodes)
        2. Inject memory context into AgentState.context
        3. Select best strategy for this task_type based on past learnings
        4. Run the LangGraph orchestrator (in a thread executor — it is sync)
        5. Save episode to memory
        6. If successful, extract and save new memories from output
        7. Update strategy success rates in agent_learnings
        8. Fire reflection hooks
        9. Return result
        """
        import uuid as _uuid

        run_id = run_id or str(_uuid.uuid4())
        agent_type = TASK_TO_AGENT.get(task_type, task_type)
        start_ts = time.monotonic()

        await self._ensure_initialized()

        # ── 1. Build memory context ──────────────────────────────────
        mem_context: dict[str, Any] = {}
        try:
            mem_context = await self._memory.build_agent_context(
                user_id=user_id,
                task_type=task_type,
                agent_type=agent_type,
            )
        except Exception as exc:
            logger.warning("Harness: memory context fetch failed, continuing without: %s", exc)

        # ── 2 & 3. Strategy selection & context injection ────────────
        strategy = "standard"
        try:
            strategy = await self._select_strategy(
                agent_type=agent_type,
                learnings=mem_context.get("learnings", []),
                blacklist=mem_context.get("blacklist", []),
            )
        except Exception as exc:
            logger.warning("Harness: strategy selection failed, using 'standard': %s", exc)

        enriched_context: dict[str, Any] = {
            **context,
            "_memory": mem_context,
            "_strategy": strategy,
        }

        # ── 4. Build AgentState and invoke orchestrator ──────────────
        state = AgentState(
            user_id=user_id,
            run_id=run_id,
            task_type=task_type,
            messages=[HumanMessage(content=str(context))],
            context=enriched_context,
            status="running",
            pending_action=None,
            result=None,
            error=None,
        )

        result_state: AgentState | None = None
        success = False
        error_msg: str | None = None

        try:
            loop = asyncio.get_event_loop()
            result_state = await loop.run_in_executor(None, orchestrator.invoke, state)
            success = result_state["status"] in {"completed", "awaiting_approval"}
            error_msg = result_state.get("error")
        except Exception as exc:
            logger.error(
                "Harness: orchestrator.invoke raised for user=%s task=%s: %s",
                user_id,
                task_type,
                exc,
            )
            error_msg = str(exc)
            result_state = {
                **state,
                "status": "failed",
                "error": error_msg,
            }

        duration_ms = int((time.monotonic() - start_ts) * 1000)

        # ── 5 & 6. Save episode, extract memories ───────────────────
        output_summary = ""
        if result_state:
            output = result_state.get("result") or result_state.get("pending_action") or {}
            output_summary = _summarise(output)
            if success and output:
                await self._extract_and_save_memories(
                    user_id=user_id,
                    agent_type=agent_type,
                    output=output,
                )

        context_summary = _summarise(context)

        try:
            await self._memory.save_episode(
                user_id=user_id,
                agent_type=agent_type,
                task_type=task_type,
                strategy=strategy,
                success=success,
                context_summary=context_summary,
                output_summary=output_summary,
            )
        except Exception as exc:
            logger.warning("Harness: save_episode failed: %s", exc)

        # ── 7. Update strategy success rate ─────────────────────────
        try:
            await self._memory.upsert_learning(
                user_id=user_id,
                agent_type=agent_type,
                learning=strategy,
                success=success,
            )
        except Exception as exc:
            logger.warning("Harness: upsert_learning failed: %s", exc)

        # ── 8. Fire reflection hooks ─────────────────────────────────
        if self._reflection_hooks:
            episode = {
                "user_id": user_id,
                "agent_type": agent_type,
                "task_type": task_type,
                "strategy": strategy,
                "success": success,
                "output_summary": output_summary,
            }
            for hook in self._reflection_hooks:
                try:
                    await hook(agent_type, [episode])
                except Exception as exc:
                    logger.warning("Harness: reflection hook raised: %s", exc)

        # ── 9. Return result ─────────────────────────────────────────
        return {
            "run_id": run_id,
            "status": result_state["status"] if result_state else "failed",
            "result": result_state.get("result") if result_state else None,
            "pending_action": result_state.get("pending_action") if result_state else None,
            "error": error_msg,
            "strategy_used": strategy,
            "duration_ms": duration_ms,
        }

    # ------------------------------------------------------------------
    # Strategy selection
    # ------------------------------------------------------------------

    async def _select_strategy(
        self,
        agent_type: str,
        learnings: list[str],
        blacklist: list[str] | None = None,
    ) -> str:
        """
        Returns a strategy hint string based on top-performing learnings.

        Priority order:
          1. Top-rated learned strategy (from past episodes via learnings param)
          2. First non-blacklisted default strategy for this agent_type
          3. "standard" fallback

        For reference, per-agent defaults:
          resume:     "emphasize metrics", "use bullet points" (via quantify_achievements)
          job_search: "filter remote only", "try Boolean search"
          email:      "short subject lines", "personalize first line"
        """
        blacklist_set = set(blacklist or [])

        # Learnings are already sorted by success_rate DESC by the DB query
        for candidate in learnings:
            if candidate not in blacklist_set:
                return candidate

        # Fall back to statically configured defaults
        for default in strategies_for_task(agent_type):
            if default not in blacklist_set:
                return default

        return "standard"

    # ------------------------------------------------------------------
    # Memory extraction from successful output
    # ------------------------------------------------------------------

    async def _extract_and_save_memories(
        self,
        user_id: str,
        agent_type: str,
        output: dict[str, Any],
    ) -> None:
        """
        Pull salient learnings from a successful output dict and persist them.
        This is a heuristic extraction — a richer version could call an LLM.
        """
        new_learnings: list[dict[str, Any]] = []

        # Example: if resume output includes match_score, infer what worked
        if agent_type == "resume":
            score = output.get("match_score")
            if score and isinstance(score, (int, float)) and score >= 80:
                new_learnings.append(
                    {"learning": "high_keyword_match", "success_rate": 1.0, "sample_count": 1}
                )

        # If email output has open_rate signal
        if agent_type == "email":
            if output.get("delivered"):
                new_learnings.append(
                    {"learning": "deliverable_email", "success_rate": 1.0, "sample_count": 1}
                )

        if new_learnings:
            await self._memory.save_learnings(
                user_id=user_id,
                agent_type=agent_type,
                learnings=new_learnings,
            )

    # ------------------------------------------------------------------
    # Reflection
    # ------------------------------------------------------------------

    async def reflect(
        self,
        agent_type: str,
        llm: Any,
        user_id: str | None = None,
    ) -> None:
        """
        Analyses recent episodes for this agent_type and extracts patterns:
        what inputs/contexts led to successful vs failed outcomes.
        Saves new learnings to agent_learnings table.

        Guard conditions (checked before running):
          - last reflection was > 24 h ago  OR
          - > 20 new episodes since last reflection

        Result timestamp stored in Redis: ``reflect:{agent_type}:last_run``
        """
        await self._ensure_initialized()

        redis_key = f"reflect:{agent_type}:last_run"
        now = datetime.now(UTC)

        # ── Check guard conditions ──────────────────────────────────
        should_reflect = False
        last_run_str = await self._memory.redis_get(redis_key)
        if last_run_str is None:
            should_reflect = True
        else:
            try:
                last_run = datetime.fromisoformat(last_run_str)
                hours_elapsed = (now - last_run).total_seconds() / 3600
                if hours_elapsed >= 24:
                    should_reflect = True
                else:
                    # Check episode count since last run
                    new_count = await self._memory.episode_count_since(
                        agent_type=agent_type,
                        since=last_run,
                        user_id=user_id,
                    )
                    if new_count >= _REFLECTION_EPISODE_THRESHOLD:
                        should_reflect = True
            except Exception:
                should_reflect = True  # unparseable timestamp → reflect

        if not should_reflect:
            logger.debug("Harness.reflect: skipping reflection for %s (guard conditions not met)", agent_type)
            return

        # ── Fetch recent episodes ────────────────────────────────────
        episodes = await self._memory.recent_episodes(
            agent_type=agent_type,
            limit=50,
            user_id=user_id,
        )
        if not episodes:
            logger.debug("Harness.reflect: no episodes found for %s", agent_type)
            await self._memory.redis_set(redis_key, now.isoformat(), _REFLECTION_REDIS_TTL)
            return

        # ── Build episode summary for the LLM ───────────────────────
        lines: list[str] = []
        for ep in episodes[:30]:  # cap tokens
            outcome = "SUCCESS" if ep.get("success") else "FAILURE"
            strategy = ep.get("strategy", "unknown")
            summary = (ep.get("output_summary") or "")[:200]
            lines.append(f"- [{outcome}] strategy={strategy} | {summary}")
        episode_text = "\n".join(lines)

        prompt = (
            f"You are an AI reflection engine for a job-search agent of type '{agent_type}'.\n"
            f"Below are recent episode outcomes:\n\n"
            f"{episode_text}\n\n"
            "Analyse the patterns. Return a JSON array of objects with keys:\n"
            '  "learning" (string), "success_rate" (float 0–1), "sample_count" (int)\n'
            "Focus on strategies and context patterns that correlate with SUCCESS vs FAILURE.\n"
            "Return ONLY the JSON array, no prose."
        )

        # ── Call LLM ────────────────────────────────────────────────
        try:
            from langchain_core.messages import HumanMessage as HM

            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: llm.invoke([HM(content=prompt)])
            )
            raw = response.content.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            learnings: list[dict[str, Any]] = json.loads(raw)
        except Exception as exc:
            logger.warning("Harness.reflect: LLM call or JSON parse failed: %s", exc)
            await self._memory.redis_set(redis_key, now.isoformat(), _REFLECTION_REDIS_TTL)
            return

        # ── Persist learnings ────────────────────────────────────────
        if user_id:
            await self._memory.save_learnings(
                user_id=user_id,
                agent_type=agent_type,
                learnings=learnings,
            )
        else:
            # Global reflection: save for each unique user seen in episodes
            seen_users: set[str] = {str(ep["user_id"]) for ep in episodes if ep.get("user_id")}
            for uid in seen_users:
                await self._memory.save_learnings(
                    user_id=uid,
                    agent_type=agent_type,
                    learnings=learnings,
                )

        logger.info(
            "Harness.reflect: saved %d learnings for agent_type=%s",
            len(learnings),
            agent_type,
        )
        await self._memory.redis_set(redis_key, now.isoformat(), _REFLECTION_REDIS_TTL)


# ──────────────────────────────────────────────────────────────────────────────
# Singleton (lazy)
# ──────────────────────────────────────────────────────────────────────────────

_harness_instance: AgentHarness | None = None
_harness_lock = asyncio.Lock()


async def get_harness() -> AgentHarness:
    """
    Return the process-level singleton AgentHarness.
    Initialised lazily on first call using app settings.
    """
    global _harness_instance
    if _harness_instance is not None:
        return _harness_instance
    async with _harness_lock:
        if _harness_instance is not None:
            return _harness_instance
        from app.core.config import settings

        _harness_instance = AgentHarness(
            db_url=settings.DATABASE_URL,
            redis_url=settings.REDIS_URL,
        )
        await _harness_instance._ensure_initialized()
        return _harness_instance


# ──────────────────────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────────────────────

def _summarise(data: Any, max_len: int = 500) -> str:
    """Produce a short text summary of a dict / list / scalar."""
    if data is None:
        return ""
    try:
        text = json.dumps(data, default=str)
    except Exception:
        text = str(data)
    return text[:max_len]
