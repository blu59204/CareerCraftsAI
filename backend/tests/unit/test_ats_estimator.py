import json

from app.services.ats_estimator import WEIGHTS, estimate_resume

RESUME = """# Ada Lovelace
ada@example.com | London
## SUMMARY
Backend engineer building reliable services.
## EXPERIENCE
### Senior Engineer | Example Ltd | London | 2020 - Present
- Reduced latency by 30% for 200 users using Python and PostgreSQL.
## EDUCATION
BSc Computer Science, University of London, 2019
## SKILLS
Python, JS, SQL, C++, C#, .NET, Go, R
"""


def test_repeatable_aliases_punctuation_and_safe_heading_pipes():
    jd = "Senior Engineer\nRequired: JavaScript, Postgres, SQL, C++, C#, .NET, Go, R"
    a = estimate_resume(RESUME, jd)
    assert json.dumps(a) == json.dumps(estimate_resume(RESUME, jd))
    assert {"javascript", "postgresql", "sql", "c++", "c#", ".net", "go", "r"} <= set(
        a["matched_keywords"]
    )
    assert not any(issue["code"] == "format_tables" for issue in a["issues"])
    assert sum(WEIGHTS.values()) == 100


def test_general_mode_renormalizes_without_fabricating_target_match():
    result = estimate_resume(RESUME)
    assert result["sub_scores"]["match"]["score"] is None
    assert result["sub_scores"]["title_fit"]["score"] is None
    assert result["mode"] == "general"
    assert result["composite_score"] == 100


def test_prose_is_not_a_heading_dates_are_not_metrics():
    result = estimate_resume(
        "# Ada\nada@example.com\n- Experience since 2020 and education since 2018."
    )
    assert result["sub_scores"]["sections"]["score"] == 0
    assert result["sub_scores"]["impact"]["score"] == 0
    risky = estimate_resume(RESUME + "\n| --- | --- |\n![photo](a.png)")
    assert risky["sub_scores"]["formatting"]["score"] < 100
