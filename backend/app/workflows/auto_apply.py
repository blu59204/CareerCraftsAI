"""Approval-bound applications in the user's own browser.

Workflow code performs no I/O; all external work belongs to activities.
Deploy only after draining workflows for the retired executor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        reserve_application_attempt,
        schedule_followup_activity,
    )
    from app.workflows.extension_activities import (
        create_extension_task_activity,
        finish_extension_task_activity,
    )


def auto_apply_workflow_id(user_id: str, job_application_id: str) -> str:
    """Stable workflow ID: starting a second workflow with this same id
    while one is already running is rejected by Temporal itself
    (WorkflowAlreadyStartedError) — the API layer catches that and returns
    the existing run instead of creating an orphan."""
    return f"auto-apply/{user_id}/{job_application_id}"


@dataclass
class AutoApplyIntent:
    user_id: str
    job_application_id: str
    mode: str = "extension"  # Kept in serialized intents for compatibility.
    # Extension mode: how long to wait for a browser to pick the task up,
    # then for the user to finish reviewing and submit.
    claim_timeout_s: int = 24 * 3600
    complete_timeout_s: int = 2 * 3600
    # Chosen by the API so it can return the run id right away; older
    # callers leave it unset and the workflow picks one.
    run_id: str | None = None
    # Started by the agent rather than the member: needs the score threshold.
    auto: bool = False


# Extension progress stages (see app/api/v1/extension.py).
EXTENSION_PROGRESS_STAGES = {"claimed", "filling", "needs_input", "review", "login_required"}
EXTENSION_TERMINAL_STAGES = {"submitted", "failed", "cancelled"}


@dataclass
class AutoApplyStatus:
    state: str
    pending_action: dict | None = None
    result: dict | None = None
    error: str | None = None


_PREP_RETRY_POLICY = RetryPolicy(maximum_attempts=3)
_RESERVE_RETRY_POLICY = RetryPolicy(maximum_attempts=3)


@workflow.defn
class AutoApplyWorkflow:
    def __init__(self) -> None:
        self._state = "created"
        self._pending_action: dict | None = None
        self._result: dict | None = None
        self._error: str | None = None
        self._cancelled = False
        self._extension_stage: str | None = None
        self._extension_outcome: str | None = None
        self._extension_details: dict = {}

    @workflow.signal
    def cancel(self) -> None:
        self._cancelled = True

    @workflow.signal
    def extension_update(self, update: dict) -> None:
        stage = update.get("stage")
        if stage in EXTENSION_PROGRESS_STAGES:
            self._extension_stage = stage
        elif stage in EXTENSION_TERMINAL_STAGES and self._extension_outcome is None:
            self._extension_stage = stage
            self._extension_outcome = stage
            self._extension_details = update.get("details") or {}

    @workflow.query
    def status(self) -> AutoApplyStatus:
        return AutoApplyStatus(
            state=self._state,
            pending_action=self._pending_action,
            result=self._result,
            error=self._error,
        )

    async def _reserve(self, intent: AutoApplyIntent) -> dict | None:
        try:
            # workflow.uuid4() (not uuid.uuid4()) — deterministic and
            # replay-safe, and generated once here so a retried
            # reserve_application_attempt activity call reuses the exact
            # same run_id instead of orphaning a new AgentRun each retry.
            run_id = intent.run_id or str(workflow.uuid4())
            return await workflow.execute_activity(
                reserve_application_attempt,
                {
                    "user_id": intent.user_id,
                    "job_application_id": intent.job_application_id,
                    "workflow_id": workflow.info().workflow_id,
                    "run_id": run_id,
                    "auto": intent.auto,
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=_RESERVE_RETRY_POLICY,
            )
        except Exception as exc:
            self._state = "failed"
            self._error = str(exc)
            self._result = {"error": str(exc)}
            return None

    @workflow.run
    async def run(self, intent: AutoApplyIntent) -> dict:
        if intent.mode != "extension":
            from temporalio.exceptions import ApplicationError

            raise ApplicationError(
                "This executor is retired; restart in the browser extension", non_retryable=True
            )
        self._state = "reserving"
        reserved = await self._reserve(intent)
        if reserved is None:
            return {"status": "failed", "result": self._result}
        return await self._run_in_extension(intent, reserved)

    async def _wait(self, condition, timeout_s: int) -> bool:
        try:
            await workflow.wait_condition(condition, timeout=timedelta(seconds=timeout_s))
            return True
        except TimeoutError:
            return False

    async def _run_in_extension(self, intent: AutoApplyIntent, reserved: dict) -> dict:
        """Hand the application to the user's browser and wait for it."""
        if reserved.get("wait_seconds"):
            # Space applications out rather than sending them in a burst.
            self._state = "pacing"
            await workflow.sleep(timedelta(seconds=reserved["wait_seconds"]))
        workflow_id = workflow.info().workflow_id
        task = await workflow.execute_activity(
            create_extension_task_activity,
            {
                "user_id": intent.user_id,
                "job_application_id": intent.job_application_id,
                "run_id": reserved["run_id"],
                "attempt_id": reserved["attempt_id"],
                "workflow_id": workflow_id,
                "job_url": reserved["job_url"],
                "company": reserved["company"],
                "role": reserved["role"],
                "pdf_document_id": reserved["pdf_document_id"],
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RESERVE_RETRY_POLICY,
        )

        self._state = "waiting_for_extension"
        claimed = await self._wait(
            lambda: self._extension_stage is not None or self._cancelled,
            intent.claim_timeout_s,
        )
        if claimed and not self._cancelled:
            self._state = "in_browser"
            await self._wait(
                lambda: self._extension_outcome is not None or self._cancelled,
                intent.complete_timeout_s,
            )

        if self._extension_outcome is not None:
            outcome = self._extension_outcome
        elif self._cancelled:
            outcome = "cancelled"
        else:
            outcome = "expired"

        finished = await workflow.execute_activity(
            finish_extension_task_activity,
            {
                "task_id": task["task_id"],
                "run_id": reserved["run_id"],
                "attempt_id": reserved["attempt_id"],
                "user_id": intent.user_id,
                "job_application_id": intent.job_application_id,
                "outcome": outcome,
                "details": self._extension_details,
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_PREP_RETRY_POLICY,
        )
        outcome = finished.get("outcome", outcome)
        self._result = {"outcome": outcome}
        if outcome == "submitted":
            self._state = "submitted"
            await workflow.execute_activity(
                schedule_followup_activity,
                {
                    "user_id": intent.user_id,
                    "job_application_id": intent.job_application_id,
                    "applied_at": finished.get("applied_at"),
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=_PREP_RETRY_POLICY,
            )
            return {"status": "completed", "result": self._result}
        self._state = outcome
        if outcome == "failed":
            self._error = (
                self._extension_details.get("error") or "Application failed in the browser"
            )
        return {"status": outcome, "result": self._result}
