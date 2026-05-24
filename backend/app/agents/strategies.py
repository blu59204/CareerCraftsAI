"""
Default strategies per agent type.

Each strategy list is ordered from most-preferred (index 0) to least-preferred.
The harness uses these as the fallback ordering when no learned preferences exist.
Strategies are plain string identifiers — they are injected into the AgentState
context so individual agents can branch their behaviour accordingly.
"""

STRATEGIES: dict[str, list[str]] = {
    "resume": [
        "quantify_achievements",
        "keyword_match",
        "clean_formatting",
    ],
    "job_search": [
        "boolean_search",
        "location_filter",
        "remote_preference",
    ],
    "email": [
        "personalize_opening",
        "short_cta",
        "follow_timeline",
    ],
    "linkedin": [
        "headline_optimization",
        "skills_endorsement",
        "connection_messaging",
    ],
}

# Canonical mapping: task_type → agent key used in STRATEGIES
TASK_TO_AGENT: dict[str, str] = {
    "resume_optimize": "resume",
    "job_search": "job_search",
    "linkedin_optimize": "linkedin",
    "email": "email",
}


def strategies_for_task(task_type: str) -> list[str]:
    """Return the default strategy list for a given task_type."""
    agent_key = TASK_TO_AGENT.get(task_type, task_type)
    return STRATEGIES.get(agent_key, [])
