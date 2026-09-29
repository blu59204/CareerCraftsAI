"""D1: location heuristic for legacy (non-positional) experience headings."""

import pytest

from app.services.resume_structure import apply_fixes, review_resume, split_heading


@pytest.mark.parametrize(
    ("heading", "employer", "location", "start", "end"),
    [
        (
            "Engineer | Tata Consultancy Services, Mumbai | 2020 - 2021",
            "Tata Consultancy Services, Mumbai",
            "",
            "2020",
            "2021",
        ),
        ("Engineer | TechCorp, Bangalore | 2021 - 2022", "TechCorp, Bangalore", "", "2021", "2022"),
        ("Engineer | Infosys, Bangalore", "Infosys, Bangalore", "", "", ""),
        ("Engineer | Johnson, Matthey", "Johnson, Matthey", "", "", ""),
        # Known region, but no dates: a lone `City, Region` stays the employer.
        ("Engineer | Pune, India", "Pune, India", "", "", ""),
        ("Engineer | Pune, India | 2021 - 2022", "", "Pune, India", "2021", "2022"),
        (
            "Engineer | Bengaluru, karnataka | 2021 - 2022",
            "",
            "Bengaluru, karnataka",
            "2021",
            "2022",
        ),
        ("Engineer | Remote | 2021 - 2022", "", "Remote", "2021", "2022"),
        ("Engineer | Remote", "", "Remote", "", ""),
        ("Engineer | work from home", "", "work from home", "", ""),
        ("Engineer | Seattle, WA | 2021", "", "Seattle, WA", "2021", ""),
        # A lowercase 2-letter code is not a region code.
        ("Engineer | Acme, co | 2021", "Acme, co", "", "2021", ""),
        ("Engineer | Acme | Pune, India | 2021", "Acme", "Pune, India", "2021", ""),
        ("Engineer | Acme | Pune | India | 2021", "Acme", "Pune, India", "2021", ""),
    ],
)
def test_legacy_heading_location_heuristic(heading, employer, location, start, end):
    entry = split_heading(heading)
    assert entry.role == "Engineer"
    assert (entry.employer, entry.location, entry.start, entry.end) == (
        employer,
        location,
        start,
        end,
    )


def test_empty_inner_slot_stays_positional():
    entry = split_heading("Engineer |  | Tata Consultancy Services, Mumbai | 2020 - 2021")
    assert (entry.employer, entry.location) == ("", "Tata Consultancy Services, Mumbai")
    entry = split_heading("Engineer | Remote |  | 2021")
    assert (entry.employer, entry.location) == ("Remote", "")


def test_adding_dates_keeps_employer_with_city():
    md = "# Asha Rao\n## EXPERIENCE\n### Engineer | Tata Consultancy Services, Mumbai\n- Built it\n"
    fixed = apply_fixes(md, experience=[{"index": 0, "start": "2020", "end": "2021"}])
    assert "### Engineer | Tata Consultancy Services, Mumbai |  | 2020 - 2021" in fixed
    review = review_resume(fixed)
    (entry,) = review["experience"]
    assert entry["employer"] == "Tata Consultancy Services, Mumbai"
    assert entry["location"] == ""
    assert "missing_employer" not in entry["issues"]
    assert all(i["code"] != "missing_employer" for i in review["issues"])
