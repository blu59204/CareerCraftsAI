"""Round-3 regression tests for the resolved-warning filter topics."""

import pytest

from app.services.resume_structure import (
    filter_resolved_warnings,
    review_resume,
    warning_topics,
)

FULL = """# Asha Rao
asha@example.com | +91 98765 43210 | Pune, India
## EXPERIENCE
### Prompt Engineer Intern | Agentic Universe Ltd | Remote | Jun 2025 - Present
- Built evaluation prompts
## EDUCATION
### B.Tech, Computer Science | Pune University |  | 2021 - 2025
## SKILLS
Python
"""


@pytest.mark.parametrize(
    "warning",
    [
        "Missing: Terraform, Kubernetes (no employer has used these)",
        "Missing dates for Kafka projects",
        "No employer has used Terraform in production.",
        "Missing Kafka experience (employer name not relevant here)",
        "Project dates are missing for the portfolio section",
    ],
)
def test_non_employment_warnings_kept_on_fixed_resume(warning):
    review = review_resume(FULL)
    assert review["issues"] == []
    assert warning_topics(warning) == set()
    assert filter_resolved_warnings([warning], review) == [warning]


@pytest.mark.parametrize(
    ("warning", "topic"),
    [
        ("The employer name is truncated.", "employer"),
        ("Employer line is incomplete in the source.", "employer"),
        ("Missing employer name for the first role.", "employer"),
        ("The employer name was cut off.", "employer"),
        ("No legal employer name is given.", "employer"),
        ("Source truncated mid-sentence: the employer reads 'X (Y Pvt.'", "employer"),
        ("No employment dates appear in the source.", "dates"),
        ("Role dates are missing.", "dates"),
        ("Missing dates for the internship.", "dates"),
        ("Education dates are missing.", "dates"),
        ("Missing start/end date for the job.", "dates"),
        ("No duration given for the position.", "dates"),
    ],
)
def test_fixable_topics_detected_and_dropped_once_fixed(warning, topic):
    assert topic in warning_topics(warning)
    assert filter_resolved_warnings([warning], review_resume(FULL)) == []
