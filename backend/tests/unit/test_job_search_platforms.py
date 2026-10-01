"""Legacy board names (the documented agent input) still reach real sources."""

import uuid
from unittest.mock import AsyncMock, patch

from app.agents import job_search


def test_legacy_platform_names_are_mapped_before_search():
    search = AsyncMock(return_value=([], []))
    state = {
        "user_id": str(uuid.uuid4()),
        "run_id": str(uuid.uuid4()),
        "context": {"search_query": "python", "platforms": ["linkedin", "Indeed", "shine"]},
    }
    with (
        patch.object(job_search, "search_all_platforms", search),
        patch("app.services.job_matching.rank_jobs", AsyncMock(return_value=([], []))),
        patch.object(job_search, "_persist_saved_jobs", return_value=0),
        patch.object(job_search, "emit"),
    ):
        result = job_search.job_search_agent_node(state)

    assert result["status"] == "completed"
    assert search.await_args.args[1] == ["jobspy", "open_apis"]
