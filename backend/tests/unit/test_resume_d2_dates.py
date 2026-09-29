"""D2 date grammar: is_date_range / split_dates (shared contract with the frontend)."""

import fitz  # PyMuPDF
import pytest

from app.services.pdf_service import generate_resume_pdf
from app.services.resume_structure import is_date_range, split_dates

VALID = [
    "Jan 2021 - Dec 2022",
    "2021-2024",
    "2021-22",
    "Q1 2021 - Q3 2022",
    "Since 2021",
    "2020 - Mid 2021",
    "Mid-2021 - 2023",
    "01.2021 - 03.2022",
    "06/2021 - 08/2022",
    "2020 to date",
    "Summer 2023",
    "May 2023",
]
INVALID = [
    "Deloitte (Summer 2023)",
    "Smart India Hackathon 2022",
    "Know Now Inc",
    "Remote",
]


@pytest.mark.parametrize("value", VALID)
def test_valid_date_ranges(value):
    assert is_date_range(value)


@pytest.mark.parametrize("value", INVALID)
def test_invalid_date_ranges(value):
    assert not is_date_range(value)


@pytest.mark.parametrize(
    "value",
    ["22", "Summer", "2021 Since", "Jan 22", "22 - 2021", "date 2021", "Mid 21", "Q5 2021"],
)
def test_token_position_rules(value):
    # 2-digit year only after `YYYY -`, Since/From only first, 'date' only in
    # 'to date', and a 4-digit year or Present word is required.
    assert not is_date_range(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2021-22", ("2021", "22")),
        ("Mid-2021 - 2023", ("Mid-2021", "2023")),
        ("Since 2021", ("Since 2021", "")),
        ("2020 to date", ("2020", "Present")),
        ("2021-2024", ("2021", "2024")),
        ("06-2021", ("06-2021", "")),
        ("Jan 2021 – Present", ("Jan 2021", "Present")),
        ("06/2021 - 08/2022", ("06/2021", "08/2022")),
    ],
)
def test_split_dates(value, expected):
    assert split_dates(value) == expected


def test_pdf_renders_short_year_range():
    pdf = generate_resume_pdf(
        "# Jane Doe\n\n## EXPERIENCE\n\n### Engineer | Acme | 2021-22\n\n- Built APIs\n",
        template="modern",
    )
    text = fitz.open(stream=pdf, filetype="pdf")[0].get_text()
    assert "2021 \u2013 22" in text
