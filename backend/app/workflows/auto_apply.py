"""AutoApplyWorkflow — one job application, from reservation to submission.

Two execution modes (settings.APPLY_EXECUTION_MODE):

* "extension" — the application is handed to the user's own browser through
  the CareerCraft extension (an extension_tasks row). The extension fills
  the form where the user is already signed in, the user presses Submit in
  the extension's review panel, and progress arrives as extension_update
  signals relayed by the API.
* "server_browser" — an isolated OpenSandbox browser is driven through
  application_workflow.run_application_stage (via activities.py), with
  approval signals from the web app.

Both share the ApplicationAttempt idempotency ledger.

Determinism: this module must never do I/O, use real wall-clock time,
randomness, or threading directly — only temporalio.workflow primitives and
workflow.execute_activity for anything that touches the outside world. The
`with workflow.unsafe.imports_passed_through()` block below is required
because activities.py imports SQLAlchemy/Playwright-touching modules that
would otherwise trip Temporal's workflow sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        apply_answers_and_resume_activity,
        reserve_application_attempt,
        run_application_stage_activity,
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
    mode: str = "server_browser"  # or "extension"
    # Extension mode: how long to wait for a browser to pick the task up,
    # then for the user to finish reviewing and submit.
    claim_timeout_s: int = 24 * 3600
    complete_timeout_s: int = 2 * 3600


# Extension progress stages (see app/api/v1/extension.py).
EXTENSION_PROGRESS_STAGES = {"claimed", "filling", "needs_input", "review", "login_required"}
EXTENSION_TERMINAL_STAGES = {"submitted", "failed", "cancelled"}


@dataclass
class AutoApplyStatus:
    state: str
    pending_action: dict | None = None
    result: dict | None = None
    error: str | None = None


# Preparation activities (navigate, extract, fill) may retry — a lost
# browser session, a transient page-load failure, etc. are all safe to
# retry since nothing external has happened yet.
_PREP_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
)
# The one activity call that can reach the actual Submit click NEVER
# retries — see run_application_stage's own claim_attempt_for_submit
# compare-and-swap for why a retry here would risk a double submission even
# with that guard: an ambiguous outcome must surface as "unknown", not be
# silently retried by Temporal on top of it.
_SUBMIT_RETRY_POLICY = RetryPolicy(maximum_attempts=1)
_RESERVE_RETRY_POLICY = RetryPolicy(maximum_attempts=3)


@workflow.defn
class AutoApplyWorkflow:
    def __init__(self) -> None:
        self._state = "created"
        self._pending_action: dict | None = None
        self._result: dict | None = None
        self._error: str | None = None
        self._answers: dict[str, str] = {}
        self._approved = False
        self._cancelled = False
        self._extension_stage: str | None = None
        self._extension_outcome: str | None = None
        self._extension_details: dict = {}

    @workflow.signal
    def provide_answers(self, answers: dict[str, str]) -> None:
        self._answers.update(answers)

    @workflow.signal
    def approve(self) -> None:
        self._approved = True

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
            run_id = str(workflow.uuid4())
            return await workflow.execute_activity(
                reserve_application_attempt,
                {
                    "user_id": intent.user_id,
                    "job_application_id": intent.job_application_id,
                    "workflow_id": workflow.info().workflow_id,
                    "run_id": run_id,
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=_RESERVE_RETRY_POLICY,
            )
        except Exception as exc:
            self._state = "failed"
            self._error = str(exc)
            self._result = {"error": str(exc)}
            return None

    async def _handle_terminal(self, stage: dict, intent: AutoApplyIntent) -> dict | None:
        """If `stage` is a terminal (non-checkpoint) result, record final
        state — scheduling the follow-up exactly once, only on a confirmed
        submission — and return it. Returns None if `stage` is instead an
        awaiting_approval checkpoint the caller must still process.

        Both call sites (the main preparation loop and the
        application_answers_required resume) route through this so
        "schedule a follow-up on submitted" can never be implemented in one
        spot and forgotten in the other.
        """
        status = stage.get("status")
        if status == "completed":
            self._result = stage.get("result")
            self._pending_action = None
            if (self._result or {}).get("outcome") == "submitted":
                self._state = "verified"
                await workflow.execute_activity(
                    schedule_followup_activity,
                    {"user_id": intent.user_id, "job_application_id": intent.job_application_id},
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=_PREP_RETRY_POLICY,
                )
            else:
                # e.g. "duplicate_suppressed" — a concurrent caller already
                # won the submit compare-and-swap.
                self._state = "completed"
            return stage

        if status == "failed":
            self._result = stage.get("result")
            self._error = (self._result or {}).get("message")
            self._pending_action = None
            # outcome "unknown" means a real side effect may have happened
            # with no way to confirm it — Temporal must never retry this
            # workflow run past this point on its own.
            outcome_unknown = (self._result or {}).get("outcome") == "unknown"
            self._state = "needs_verification" if outcome_unknown else "failed"
            return stage

        return None

    @workflow.run
    async def run(self, intent: AutoApplyIntent) -> dict:
        self._state = "reserving"
        reserved = await self._reserve(intent)
        if reserved is None:
            return {"status": "failed", "result": self._result}

        if intent.mode == "extension":
            return await self._run_in_extension(intent, reserved)

        run_id = reserved["run_id"]
        pending: dict = {
            "type": "browser_prepare",
            "job_url": reserved["job_url"],
            "company": reserved["company"],
            "role": reserved["role"],
            "attempt_id": reserved["attempt_id"],
            "pdf_document_id": reserved["pdf_document_id"],
            "resume_sha256": reserved["resume_sha256"],
        }

        self._state = "preparing"
        while True:
            if self._cancelled:
                self._state = "cancelled"
                return {"status": "cancelled", "result": {}}

            is_submit_attempt = pending["type"] == "browser_review"
            stage = await workflow.execute_activity(
                run_application_stage_activity,
                {"run_id": run_id, "pending": pending},
                start_to_close_timeout=timedelta(seconds=120),
                heartbeat_timeout=timedelta(seconds=30),
                retry_policy=_SUBMIT_RETRY_POLICY if is_submit_attempt else _PREP_RETRY_POLICY,
            )

            finished = await self._handle_terminal(stage, intent)
            if finished is not None:
                return finished

            # status == "awaiting_approval": the activity returned a
            # checkpoint (browser_input / browser_review /
            # application_answers_required). Wait for the matching signal.
            action = stage.get("pending_action") or {}
            action_type = action.get("type")
            self._pending_action = action
            pending = {**pending, **action}

            if action_type == "application_answers_required":
                self._state = "awaiting_input"
                # Cleared after use, never before waiting — see _await_approval.
                await workflow.wait_condition(lambda: bool(self._answers) or self._cancelled)
                if self._cancelled:
                    self._state = "cancelled"
                    return {"status": "cancelled", "result": {}}
                answers, self._answers = dict(self._answers), {}
                answered = await workflow.execute_activity(
                    apply_answers_and_resume_activity,
                    {
                        "run_id": run_id,
                        "user_id": intent.user_id,
                        "answers": answers,
                        "fields": action.get("fields", []),
                        "pending": pending,
                    },
                    start_to_close_timeout=timedelta(seconds=120),
                    heartbeat_timeout=timedelta(seconds=30),
                    retry_policy=_PREP_RETRY_POLICY,
                )
                finished = await self._handle_terminal(answered, intent)
                if finished is not None:
                    return finished
                next_action = answered.get("pending_action") or {}
                next_type = next_action.get("type", "browser_input")
                self._pending_action = next_action
                pending = {**pending, **next_action, "type": next_type}
                needs_more_answers = next_type == "application_answers_required"
                self._state = "awaiting_input" if needs_more_answers else "preparing"
                continue

            # browser_review (final submit) and browser_input (form still
            # incomplete — e.g. login/verification needed in the live
            # browser) both wait for the same generic approval signal: the
            # frontend button ("Continue preparation" / "Approve final
            # submission") posts to one generic approve endpoint for every
            # checkpoint type, so the workflow waits the same way rather than
            # auto-retrying browser_input on a timer.
            is_review = action_type == "browser_review"
            self._state = "awaiting_approval" if is_review else "awaiting_browser_input"
            # The flag is cleared after it is consumed, not before waiting: an
            # approval processed in the same workflow task as the activity
            # result must not be wiped out.
            await workflow.wait_condition(lambda: self._approved or self._cancelled)
            if self._cancelled:
                self._state = "cancelled"
                return {"status": "cancelled", "result": {}}
            self._approved = False
            self._state = "submitting" if is_review else "preparing"

    async def _wait(self, condition, timeout_s: int) -> bool:
        try:
            await workflow.wait_condition(condition, timeout=timedelta(seconds=timeout_s))
            return True
        except TimeoutError:
            return False

    async def _run_in_extension(self, intent: AutoApplyIntent, reserved: dict) -> dict:
        """Hand the application to the user's browser and wait for it."""
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
