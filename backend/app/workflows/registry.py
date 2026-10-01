"""Every workflow and activity the worker hosts — one list, so a new
workflow cannot be started by the API without a worker able to run it."""

from app.workflows.activities import (
    reserve_application_attempt,
    schedule_followup_activity,
)
from app.workflows.agent_activities import (
    continue_agent_run_activity,
    execute_agent_run_activity,
    expire_agent_run_activity,
)
from app.workflows.agent_run import AgentRunWorkflow
from app.workflows.auto_apply import AutoApplyWorkflow
from app.workflows.extension_activities import (
    create_extension_task_activity,
    finish_extension_task_activity,
)
from app.workflows.followup import FollowupWorkflow
from app.workflows.job_activities import (
    daily_search_activity,
    draft_followup_activity,
    fail_job_search_activity,
    maintenance_activity,
    run_job_search_activity,
    refresh_job_catalog_activity,
)
from app.workflows.job_search import JobSearchWorkflow
from app.workflows.scheduled import (
    DailySearchWorkflow,
    MaintenanceWorkflow,
    JobCatalogRefreshWorkflow,
)

WORKFLOWS = [
    JobCatalogRefreshWorkflow,
    AgentRunWorkflow,
    AutoApplyWorkflow,
    JobSearchWorkflow,
    FollowupWorkflow,
    DailySearchWorkflow,
    MaintenanceWorkflow,
]

ACTIVITIES = [
    refresh_job_catalog_activity,
    execute_agent_run_activity,
    continue_agent_run_activity,
    expire_agent_run_activity,
    reserve_application_attempt,
    schedule_followup_activity,
    create_extension_task_activity,
    finish_extension_task_activity,
    run_job_search_activity,
    fail_job_search_activity,
    draft_followup_activity,
    daily_search_activity,
    maintenance_activity,
]
