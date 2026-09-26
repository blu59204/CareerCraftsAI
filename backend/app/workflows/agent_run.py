"""AgentRunWorkflow — durable execution of one POST /agents/run request.

Replaces the old WorkflowTask outbox + BullMQ dispatcher. The workflow is
the execution ledger; the agent_runs row stays the user-facing record that
the activities keep in sync (status, output, SSE events).

    execute ──► completed / failed
       │
       └──► awaiting_approval ──(decide signal)──► continue ──► ... (loop)
                     │
                     └──(approval timeout)──► expired

Determinism: no I/O here — only workflow primitives and activities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.agent_activities import (
        continue_agent_run_activity,
        execute_agent_run_activity,
        expire_agent_run_activity,
    )


def agent_run_workflow_id(run_id: str) -> str:
    return f"agent-run/{run_id}"


@dataclass
class AgentRunInput:
    run_id: str
    user_id: str
    # Upper bound for one execute/continue activity.
    activity_timeout_s: int = 330
    # How long a checkpoint waits for the user before the run expires.
    approval_timeout_s: int = 48 * 3600
    # Set when the run starts from an already-approved action (e.g. an email
    # queued by an approved auto-apply batch): skip execution and continue.
    initial_continuation: dict | None = None
    # The run was produced outside a workflow (an inline API route or a
    # follow-up draft) and is already waiting at a checkpoint: skip
    # execution and wait for the decide signal (delivered by signal-with-start).
    start_at_checkpoint: bool = False


@dataclass
class ApprovalDecision:
    approved: bool
    action_type: str = ""
    continuation: dict | None = None


# Agent execution is LLM calls plus read-only tools, so one retry of an
# infrastructure failure (worker crash, DB blip) is safe.
_EXECUTE_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_attempts=2,
    non_retryable_error_types=["ValueError"],
)
# A continuation can send an email or click Submit — never replay it.
_CONTINUE_RETRY = RetryPolicy(maximum_attempts=1)
_BOOKKEEPING_RETRY = RetryPolicy(maximum_attempts=5)


@workflow.defn
class AgentRunWorkflow:
    def __init__(self) -> None:
        self._state = "queued"
        self._decision: ApprovalDecision | None = None

    @workflow.signal
    def decide(self, decision: ApprovalDecision) -> None:
        self._decision = decision

    @workflow.query
    def status(self) -> str:
        return self._state

    @workflow.run
    async def run(self, inp: AgentRunInput) -> dict:
        timeout = timedelta(seconds=inp.activity_timeout_s)
        if inp.start_at_checkpoint:
            stage: dict = {"status": "awaiting_approval"}
        elif inp.initial_continuation is not None:
            self._state = "continuing"
            stage = await workflow.execute_activity(
                continue_agent_run_activity,
                {"run_id": inp.run_id, "continuation": inp.initial_continuation},
                start_to_close_timeout=timeout,
                retry_policy=_CONTINUE_RETRY,
            )
        else:
            self._state = "running"
            stage = await workflow.execute_activity(
                execute_agent_run_activity,
                {"run_id": inp.run_id},
                start_to_close_timeout=timeout,
                retry_policy=_EXECUTE_RETRY,
            )

        while stage.get("status") == "awaiting_approval":
            self._state = "awaiting_approval"
            # A decision is cleared only after it is consumed, never before
            # waiting: a signal that lands in the same workflow task as the
            # activity result must not be lost.
            try:
                await workflow.wait_condition(
                    lambda: self._decision is not None,
                    timeout=timedelta(seconds=inp.approval_timeout_s),
                )
            except TimeoutError:
                self._state = "expired"
                await workflow.execute_activity(
                    expire_agent_run_activity,
                    {"run_id": inp.run_id},
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=_BOOKKEEPING_RETRY,
                )
                return {"status": "expired"}

            decision, self._decision = self._decision, None
            if not decision.approved:
                # The API already recorded the cancellation on the run row.
                self._state = "cancelled"
                return {"status": "cancelled"}

            self._state = "continuing"
            stage = await workflow.execute_activity(
                continue_agent_run_activity,
                {"run_id": inp.run_id, "continuation": decision.continuation or {}},
                start_to_close_timeout=timeout,
                retry_policy=_CONTINUE_RETRY,
            )

        self._state = stage.get("status", "failed")
        return stage
