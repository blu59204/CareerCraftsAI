"""resume_structure: parse, audit and deterministically patch resume Markdown."""

import pytest

from app.services.resume_structure import (
    apply_fixes,
    apply_saved_facts,
    clean_placeholders,
    ensure_contact,
    filter_resolved_warnings,
    parse_contact,
    review_resume,
    split_heading,
)

# The shape the user reported: truncated employer, no dates, no education,
# no contact details.
SPARSE = """# Asha Rao
## SUMMARY
Prompt engineer focused on LLM evaluation.
## EXPERIENCE
### Prompt Engineer Intern | Agentic Universe (Qultured Media Pvt.
- Built evaluation prompts for Nova LLM on AWS
- Deployed Vertex AI pipelines on Google Cloud
## SKILLS
**AI:** Prompt engineering, RAG
"""


def _codes(review):
    return sorted(i["code"] for i in review["issues"])


def test_split_heading_all_parts():
    p = split_heading("Backend Engineer | Acme | Pune, India | Jan 2021 - Present")
    assert (p.role, p.employer, p.location, p.start, p.end) == (
        "Backend Engineer", "Acme", "Pune, India", "Jan 2021", "Present",
    )


@pytest.mark.parametrize("dates,start,end", [
    ("2021-2024", "2021", "2024"),
    ("Jun 2024 – Aug 2024", "Jun 2024", "Aug 2024"),
    ("2020 to 2022", "2020", "2022"),
    ("May 2023", "May 2023", ""),
])
def test_split_heading_date_formats(dates, start, end):
    p = split_heading(f"Engineer | Acme | {dates}")
    assert (p.employer, p.start, p.end) == ("Acme", start, end)


def test_review_flags_every_reported_gap():
    review = review_resume(SPARSE)
    assert _codes(review) == [
        "missing_dates", "missing_education", "missing_email", "missing_phone",
        "truncated_employer",
    ]
    [entry] = review["experience"]
    assert entry["role"] == "Prompt Engineer Intern"
    assert entry["employer"] == "Agentic Universe (Qultured Media Pvt."
    assert set(entry["issues"]) == {"truncated_employer", "missing_dates"}


def test_apply_fixes_resolves_all_gaps():
    fixed = apply_fixes(
        SPARSE,
        contact={"email": "asha@example.com", "phone": "+91 98765 43210",
                 "location": "Pune, India"},
        experience=[{
            "index": 0, "employer": "Agentic Universe (Qultured Media Pvt. Ltd.)",
            "location": "Remote", "start": "Jun 2025", "end": "Present",
        }],
        education=[{
            "degree": "B.Tech, Computer Science", "institution": "Pune University",
            "start": "2021", "end": "2025", "details": "CGPA 8.4/10",
        }],
    )
    review = review_resume(fixed)
    assert review["issues"] == []
    assert "asha@example.com | +91 98765 43210 | Pune, India" in fixed
    assert (
        "### Prompt Engineer Intern | Agentic Universe (Qultured Media Pvt. Ltd.) | Remote | "
        "Jun 2025 - Present" in fixed
    )
    # Education lands after experience, before skills.
    assert fixed.index("## EXPERIENCE") < fixed.index("## EDUCATION") < fixed.index("## SKILLS")
    assert "- CGPA 8.4/10" in fixed
    # Bullets are untouched.
    assert "- Built evaluation prompts for Nova LLM on AWS" in fixed


def test_contact_merge_keeps_existing_and_empty_string_removes():
    text = "# Jane\njane@example.com | +1 555 010 0199\n## SKILLS\nPython\n"
    out = apply_fixes(text, contact={"linkedin": "linkedin.com/in/jane", "phone": ""})
    assert parse_contact(out) == {
        "email": "jane@example.com", "phone": "", "location": "",
        "linkedin": "linkedin.com/in/jane", "github": "", "portfolio": "",
    }


def test_user_values_cannot_break_markdown_shape():
    out = apply_fixes(SPARSE, experience=[{"index": 0, "employer": "## Evil | Corp\n### x"}])
    heading = next(ln for ln in out.splitlines() if ln.startswith("### Prompt"))
    assert heading == "### Prompt Engineer Intern | Evil / Corp ### x"

    def heads(text):
        return [ln for ln in text.splitlines() if ln.startswith("#")]

    assert len(heads(out)) == len(heads(SPARSE))


def test_unknown_entry_index_raises():
    with pytest.raises(ValueError):
        apply_fixes(SPARSE, experience=[{"index": 3, "start": "2020"}])


def test_name_added_when_missing():
    out = apply_fixes("## SKILLS\nPython\n", full_name="Jane Doe")
    assert out.startswith("# Jane Doe\n")


def test_clean_placeholders():
    text = (
        "# Jane\nNOT_PROVIDED\n## EXPERIENCE\n"
        "### Engineer | Acme | NOT_PROVIDED\n- Built APIs\n"
        "## EDUCATION\nNOT_PROVIDED\n## SKILLS\nPython\n"
    )
    out = clean_placeholders(text)
    assert "NOT_PROVIDED" not in out
    assert "### Engineer | Acme" in out
    assert "## EDUCATION" not in out  # empty section dropped
    assert "## SKILLS\nPython" in out


def test_ensure_contact_never_overwrites():
    text = "# Jane\njane@old.com\n## SKILLS\nPython\n"
    out = ensure_contact(text, {"email": "jane@new.com", "phone": "+1 555 010 0199"})
    assert "jane@old.com | +1 555 010 0199" in out
    assert "jane@new.com" not in out


def test_saved_facts_reapply_to_a_new_draft():
    facts = {
        "experience": [{
            "role": "Prompt Engineer Intern",
            "employer_match": "Agentic Universe (Qultured Media Pvt.",
            "employer": "Agentic Universe (Qultured Media Pvt. Ltd.)",
            "location": "Remote", "start": "Jun 2025", "end": "Present",
        }],
        "education": [{"degree": "B.Tech", "institution": "Pune University", "end": "2025"}],
    }
    review = review_resume(apply_saved_facts(SPARSE, facts))
    assert _codes(review) == ["missing_email", "missing_phone"]


def test_resolved_warnings_are_hidden_but_skill_gaps_kept():
    warnings = [
        "The resume source is truncated mid-sentence: the employer line reads 'X (Y Pvt.'",
        "No employment dates, duration, or location appear anywhere in the source.",
        "No education section exists in the source; it is marked NOT_PROVIDED.",
        "The JD requires Azure cloud architecture; the source shows only AWS.",
        "Contact details (email, phone) were intentionally omitted per the source.",
    ]
    fixed = apply_fixes(
        SPARSE,
        experience=[{"index": 0, "employer": "Agentic Universe Ltd",
                     "start": "2025", "end": "Present"}],
        education=[{"degree": "B.Tech", "institution": "Pune University"}],
    )
    kept = filter_resolved_warnings(warnings, review_resume(fixed))
    # Contact is still missing, Azure is a real gap — both stay.
    assert kept == [warnings[3], warnings[4]]
