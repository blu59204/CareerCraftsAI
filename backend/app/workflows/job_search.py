"""JobSearchWorkflow — one POST /jobs/search run (was a BullMQ job)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from app.workflows.job_activities import fail_job_search_activity, run_job_search_activity


def job_search_workflow_id(run_id: str) -> str:
    return f"job-search/{run_id}"


@dataclass
class JobSearchInput:
    run_id: str
    user_id: str
    params: dict = field(default_factory=dict)


@workflow.defn
class JobSearchWorkflow:
    @workflow.run
    async def run(self, inp: JobSearchInput) -> dict:
        try:
            # The search itself enforces a 120s budget; saved jobs are
            # de-duplicated on (user, url), so one retry is harmless.
            return await workflow.execute_activity(
                run_job_search_activity,
                {**inp.params, "user_id": inp.user_id, "run_id": inp.run_id},
                start_to_close_timeout=timedelta(seconds=180),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
        except ActivityError:
            await workflow.execute_activity(
                fail_job_search_activity,
                {"run_id": inp.run_id},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            return {"status": "failed"}
