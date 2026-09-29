"""resume_structure: parse, audit and deterministically patch resume Markdown."""

import pytest

from app.services.resume_structure import (
    EntryParts,
    apply_fixes,
    apply_saved_facts,
    clean_field,
    clean_placeholders,
    ensure_contact,
    filter_resolved_warnings,
    format_heading,
    is_date_range,
    is_placeholder,
    parse_contact,
    review_resume,
    split_dates,
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
        "Backend Engineer",
        "Acme",
        "Pune, India",
        "Jan 2021",
        "Present",
    )


@pytest.mark.parametrize(
    "dates,start,end",
    [
        ("2021-2024", "2021", "2024"),
        ("Jun 2024 – Aug 2024", "Jun 2024", "Aug 2024"),
        ("2020 to 2022", "2020", "2022"),
        ("May 2023", "May 2023", ""),
    ],
)
def test_split_heading_date_formats(dates, start, end):
    p = split_heading(f"Engineer | Acme | {dates}")
    assert (p.employer, p.start, p.end) == ("Acme", start, end)


def test_review_flags_every_reported_gap():
    review = review_resume(SPARSE)
    assert _codes(review) == [
        "missing_dates",
        "missing_education",
        "missing_email",
        "missing_phone",
        "truncated_employer",
    ]
    [entry] = review["experience"]
    assert entry["role"] == "Prompt Engineer Intern"
    assert entry["employer"] == "Agentic Universe (Qultured Media Pvt."
    assert set(entry["issues"]) == {"truncated_employer", "missing_dates"}


def test_apply_fixes_resolves_all_gaps():
    fixed = apply_fixes(
        SPARSE,
        contact={
            "email": "asha@example.com",
            "phone": "+91 98765 43210",
            "location": "Pune, India",
        },
        experience=[
            {
                "index": 0,
                "employer": "Agentic Universe (Qultured Media Pvt. Ltd.)",
                "location": "Remote",
                "start": "Jun 2025",
                "end": "Present",
            }
        ],
        education=[
            {
                "degree": "B.Tech, Computer Science",
                "institution": "Pune University",
                "start": "2021",
                "end": "2025",
                "details": "CGPA 8.4/10",
            }
        ],
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
        "email": "jane@example.com",
        "phone": "",
        "location": "",
        "linkedin": "linkedin.com/in/jane",
        "github": "",
        "portfolio": "",
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
        "experience": [
            {
                "role": "Prompt Engineer Intern",
                "employer_match": "Agentic Universe (Qultured Media Pvt.",
                "employer": "Agentic Universe (Qultured Media Pvt. Ltd.)",
                "location": "Remote",
                "start": "Jun 2025",
                "end": "Present",
            }
        ],
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
        experience=[
            {"index": 0, "employer": "Agentic Universe Ltd", "start": "2025", "end": "Present"}
        ],
        # Education needs its dates too: an undated education entry keeps the
        # "dates" topic open.
        education=[{"degree": "B.Tech", "institution": "Pune University", "end": "2025"}],
    )
    kept = filter_resolved_warnings(warnings, review_resume(fixed))
    # Contact is still missing, Azure is a real gap — both stay.
    assert kept == [warnings[3], warnings[4]]


# ── Regression tests for the code-review findings ───────────────────────────

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


def _heading_lines(text):
    return [ln for ln in text.splitlines() if ln.startswith("#")]


def _line_with(text, needle):
    return next(ln for ln in text.splitlines() if needle in ln)


# 1. contact parts keep inner underscores


def test_parse_contact_keeps_underscores():
    text = "# Jane\njane_doe@example.com | github.com/jane_doe\n## SKILLS\nPython\n"
    contact = parse_contact(text)
    assert contact["email"] == "jane_doe@example.com"
    assert contact["github"] == "github.com/jane_doe"


def test_parse_contact_strips_only_surrounding_emphasis():
    text = "# Jane\n**jane_doe@example.com** | `+1 555 010 0199`\n## SKILLS\nPython\n"
    contact = parse_contact(text)
    assert (contact["email"], contact["phone"]) == ("jane_doe@example.com", "+1 555 010 0199")


# 2. labeled parts, extras preserved, in-place contact edits

LABELED = (
    "# Jane\nEmail: jane@x.com | Tel: +1 555 010 0199 | kaggle.com/jane | portfolio.dev | "
    "Sector 62, Noida\n## SKILLS\nPython\n"
)


def test_labeled_contact_parts_are_classified():
    assert parse_contact(LABELED) == {
        "email": "jane@x.com",
        "phone": "+1 555 010 0199",
        "location": "Sector 62, Noida",
        "linkedin": "",
        "github": "",
        "portfolio": "kaggle.com/jane",
    }


def test_contact_update_edits_parts_in_place():
    out = apply_fixes(
        LABELED,
        contact={
            "phone": "+1 555 010 0100",
            "linkedin": "linkedin.com/in/jane",
            "email": None,
        },
    )
    assert _line_with(out, "jane@x.com") == (
        "Email: jane@x.com | Tel: +1 555 010 0100 | kaggle.com/jane | portfolio.dev | "
        "Sector 62, Noida | linkedin.com/in/jane"
    )
    removed = apply_fixes(LABELED, contact={"email": ""})
    assert _line_with(removed, "Tel:") == (
        "Tel: +1 555 010 0199 | kaggle.com/jane | portfolio.dev | Sector 62, Noida"
    )


def test_contact_update_keeps_untouched_separators():
    text = "# Jane\njane@x.com · +1 555 010 0199\n## SKILLS\nPython\n"
    out = apply_fixes(text, contact={"location": "Pune"})
    assert "jane@x.com · +1 555 010 0199 | Pune" in out


def test_clean_field_neutralizes_contact_separators():
    assert clean_field("a | b; c · d • e") == "a / b, c d e"
    text = "# Jane\njane@x.com\n## SKILLS\nPython\n"
    out = apply_fixes(text, contact={"location": "Pune; India"})
    assert parse_contact(out)["location"] == "Pune, India"
    assert "jane@x.com | Pune, India" in out


# 3. plain-text resumes

PLAIN = """Jane Doe
jane@example.com | +1 555 010 0199
EXPERIENCE
Software Engineer, Acme, 2019 - 2021
Built payment APIs
EDUCATION
B.Tech, CS, IIT Bombay, 2015 - 2019
"""


def test_plain_text_contact_rewrite_keeps_body_lines():
    out = apply_fixes(PLAIN, full_name="Jane Doe", contact={"linkedin": "linkedin.com/in/jane"})
    assert "Software Engineer, Acme, 2019 - 2021" in out
    assert "B.Tech, CS, IIT Bombay, 2015 - 2019" in out
    assert "jane@example.com | +1 555 010 0199 | linkedin.com/in/jane" in out
    # No duplicate `# Jane Doe` above the existing plain name line.
    assert "# Jane Doe" not in out
    assert out.count("Jane Doe") == 1


def test_plain_text_contact_inserted_after_plain_name():
    text = "Jane Doe\nSoftware Engineer, Acme, 2019 - 2021\n"
    out = apply_fixes(text, full_name="jane doe", contact={"email": "jane@example.com"})
    assert out.splitlines() == [
        "Jane Doe",
        "jane@example.com",
        "Software Engineer, Acme, 2019 - 2021",
    ]


def test_plain_text_review_skips_unjudgeable_education():
    review = review_resume(PLAIN)
    assert _codes(review) == []
    assert review["contact"]["email"] == "jane@example.com"
    assert review["contact"]["phone"] == "+1 555 010 0199"
    assert review["contact"]["location"] == ""


def test_date_ranges_are_not_contact_lines():
    text = "# Jane\n## EXPERIENCE\nSoftware Engineer, Acme, 2019 - 2021\n"
    assert parse_contact(text)["phone"] == ""
    header = "Jane Doe\n2019 - 2021\n"
    assert parse_contact(header)["phone"] == ""


# 4. warning filter only drops resolved, fixable gaps


@pytest.mark.parametrize(
    "warning",
    [
        "Keep up-to-date Kubernetes skills",
        "email marketing tools (Mailchimp)",
        "Missing email marketing tools (Mailchimp) experience.",
        "phone-based customer support",
        "No phone-based customer support experience.",
        "JD prefers a Master's degree; education shows only a BSc",
        "Graduation date for the BSc is missing",
        "dates look fine but the JD requires Azure",
        "5 years duration of Java",
    ],
)
def test_real_gaps_are_kept_on_a_fixed_resume(warning):
    review = review_resume(FULL)
    assert review["issues"] == []
    assert filter_resolved_warnings([warning], review) == [warning]


ORIGINAL_WARNINGS = [
    "The resume source is truncated mid-sentence: the employer line reads "
    "'Agentic Universe (Qultured Media Pvt.'",
    "No employment dates, duration, or location appear anywhere in the source.",
    "No education section exists in the source; it is marked NOT_PROVIDED.",
    "The JD requires Azure cloud architecture; the source shows only AWS.",
    "Contact details (email, phone) were intentionally omitted per the source.",
    "The role targets a senior engineer; the source shows an internship-level role.",
]


def test_original_warnings_dropped_once_fixed():
    kept = filter_resolved_warnings(ORIGINAL_WARNINGS, review_resume(FULL))
    assert kept == [ORIGINAL_WARNINGS[3], ORIGINAL_WARNINGS[5]]


def test_original_warnings_kept_while_gaps_open():
    assert filter_resolved_warnings(ORIGINAL_WARNINGS, review_resume(SPARSE)) == (ORIGINAL_WARNINGS)


def test_education_date_gap_keeps_dates_warning_open():
    text = FULL.replace("|  | 2021 - 2025", "")
    review = review_resume(text)
    assert review["education"][0]["issues"] == ["missing_dates"]
    kept = filter_resolved_warnings([ORIGINAL_WARNINGS[1]], review)
    assert kept == [ORIGINAL_WARNINGS[1]]


def test_filter_resolved_warnings_signature():
    assert filter_resolved_warnings([], review_resume(FULL)) == []


# The user's real warning list: fixable gaps drop once fixed even when another
# clause mentions a requirement; gaps against the JD stay.
USER_WARNINGS = [
    "The resume source is truncated mid-sentence: the employer line reads 'Agentic Universe "
    "(Qultured Media Pvt.' — the full legal employer name is incomplete and must be supplied "
    "by the user.",
    "No employment dates, duration, or location appear anywhere in the source; ATS systems and "
    "recruiters will expect a start/end date for the Prompt Engineer Intern role. This is "
    "marked NOT_PROVIDED and cannot be inferred.",
    "No education section exists in the source; it is marked NOT_PROVIDED. Add it if the "
    "target roles require a degree.",
    "The JD requires Azure cloud architecture; the source shows only AWS (Nova LLM) and Google "
    "Cloud (Vertex AI). Azure is listed in keywords_missing and was deliberately not added to "
    "the resume body — do not add it unless it is genuinely part of your experience.",
    "The JD requires ModelOps/LLMOps, microservices, event-driven architectures, architecture "
    "governance, AI design patterns, responsible AI, and product/stakeholder management. None "
    "of these appear in the source and none were added; treat each as a genuine gap to "
    "address in a cover letter or to build.",
    "The JD is written at enterprise-architect seniority while the source's only role is an "
    "internship. Title alignment is weak, and inflating the title to close that gap would be "
    "untruthful.",
    "Contact details (email, phone) were intentionally omitted per the source. Add them before "
    "submitting anywhere.",
    "No instruction-injection attempt was detected in the job description text.",
    "At roughly one page and with a single truncated role, this resume is sparse relative to "
    "the JD — the tailoring is limited by what the source actually contains.",
]


def test_user_warnings_dropped_once_fixed_even_with_requirement_clause():
    kept = filter_resolved_warnings(USER_WARNINGS, review_resume(FULL))
    assert kept == [USER_WARNINGS[i] for i in (3, 4, 5, 7, 8)]


def test_user_warnings_all_kept_while_gaps_open():
    assert filter_resolved_warnings(USER_WARNINGS, review_resume(SPARSE)) == USER_WARNINGS


@pytest.mark.parametrize(
    "warning",
    [
        "The role requires a degree and no education section is listed.",
        "Missing dates are required by the employer.",
    ],
)
def test_requirement_in_the_same_clause_keeps_warning(warning):
    assert filter_resolved_warnings([warning], review_resume(FULL)) == [warning]


# 5. saved facts attach only to the right role


def _exp(role_line):
    return f"# Jane\n## EXPERIENCE\n### {role_line}\n- Built things\n"


def test_saved_facts_do_not_attach_to_a_different_role():
    text = _exp("Senior Software Engineer | Beta Labs")
    facts = {
        "experience": [
            {"role": "Software Engineer", "employer": "Acme", "start": "2019", "end": "2021"}
        ]
    }
    assert apply_saved_facts(text, facts) == text


def test_saved_facts_do_not_attach_to_a_different_employer():
    text = _exp("Software Engineer | Beta Labs")
    facts = {
        "experience": [
            {"role": "Software Engineer", "employer": "Acme Corp", "start": "2019", "end": "2021"}
        ]
    }
    assert apply_saved_facts(text, facts) == text


def test_saved_facts_fill_empty_employer_on_unique_role_match():
    text = _exp("Software Engineer")
    facts = {
        "experience": [
            {"role": "software engineer.", "employer": "Acme Corp", "start": "2019", "end": "2021"}
        ]
    }
    out = apply_saved_facts(text, facts)
    assert "### Software Engineer | Acme Corp |  | 2019 - 2021" in out


def test_saved_facts_ambiguous_role_only_match_is_skipped():
    text = _exp("Software Engineer")
    facts = {
        "experience": [
            {"role": "Software Engineer", "employer": "Acme Corp", "start": "2019"},
            {"role": "Software Engineer", "employer": "Beta Labs", "start": "2021"},
        ]
    }
    assert apply_saved_facts(text, facts) == text


def test_saved_fact_matching_two_entries_is_skipped():
    text = (
        "# Jane\n## EXPERIENCE\n### Software Engineer | Acme\n- a\n"
        "### Software Engineer | Acme\n- b\n"
    )
    facts = {"experience": [{"role": "Software Engineer", "employer": "Acme", "start": "2019"}]}
    assert apply_saved_facts(text, facts) == text


def test_saved_facts_normalize_punctuation_and_case():
    text = _exp("Software Engineer - Backend | ACME, Inc.")
    facts = {
        "experience": [
            {
                "role": "software engineer (backend)",
                "employer": "Acme Inc",
                "start": "2019",
                "end": "2021",
            }
        ]
    }
    out = apply_saved_facts(text, facts)
    assert "### Software Engineer - Backend | ACME, Inc. |  | 2019 - 2021" in out


def test_saved_facts_complete_a_truncated_employer_by_prefix():
    text = _exp("Intern | Agentic Universe (Qultured Media Pvt.")
    facts = {
        "experience": [
            {"role": "Intern", "employer": "Agentic Universe (Qultured Media Pvt. Ltd.)"}
        ]
    }
    out = apply_saved_facts(text, facts)
    assert "### Intern | Agentic Universe (Qultured Media Pvt. Ltd.)" in out


# 6. placeholders


@pytest.mark.parametrize(
    "line",
    [
        "The vendor had not provided patches",
        "Budget was not provided, so we cut scope",
        "- NA",
        "- Unknown",
    ],
)
def test_clean_placeholders_keeps_real_text(line):
    out = clean_placeholders(f"# Jane\n## SUMMARY\n{line}\n")
    assert line in out.splitlines()


def test_clean_placeholders_removes_uppercase_tokens_only():
    out = clean_placeholders("# Jane\n## SUMMARY\nBudget was NOT_PROVIDED, so we cut scope\n")
    assert "Budget was, so we cut scope" in out
    out = clean_placeholders("# Jane\n## SUMMARY\nLed [NOT PROVIDED] team (NOT_PROVIDED)\n")
    assert "Led team" in out


def test_clean_placeholders_drops_placeholder_parts_and_lines():
    text = "# Jane\njane@x.com | N/A | tbd\n[NOT_PROVIDED]\n## SKILLS\nPython\n"
    out = clean_placeholders(text)
    assert out == "# Jane\njane@x.com\n## SKILLS\nPython\n"


def test_clean_placeholders_keeps_heading_slots_positional():
    out = clean_placeholders(
        "## EXPERIENCE\n### Engineer | NOT_PROVIDED | Pune | 2021 - 2022\n- x\n"
    )
    assert "### Engineer |  | Pune | 2021 - 2022" in out
    parts = split_heading("Engineer |  | Pune | 2021 - 2022")
    assert (parts.employer, parts.location) == ("", "Pune")


def test_clean_placeholders_only_placeholder_is_empty():
    assert clean_placeholders("NOT_PROVIDED") == ""
    assert clean_placeholders("  \n") == ""


def test_is_placeholder_is_case_insensitive_part_check():
    assert is_placeholder("n/a") and is_placeholder("Not_Provided") and is_placeholder("[TBD]")
    assert not is_placeholder("not provided yet")
    assert not is_placeholder("")


# 7. positional heading slots


def test_legacy_two_part_location_is_not_an_employer():
    parts = split_heading("Engineer | Remote | 2021 - 2022")
    assert (parts.role, parts.employer, parts.location) == ("Engineer", "", "Remote")
    review = review_resume(_exp("Engineer | Remote | 2021 - 2022"))
    assert "missing_employer" in _codes(review)
    assert review["experience"][0]["issues"] == ["missing_employer"]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Engineer |  | Remote | Jan 2021 - Dec 2022", ("Engineer", "", "Remote", "Jan 2021")),
        ("Engineer | Acme |  | 2021 - 2022", ("Engineer", "Acme", "", "2021")),
        ("Engineer | Pune, India | 2021", ("Engineer", "", "Pune, India", "2021")),
        ("Engineer | Acme, Inc | 2021", ("Engineer", "Acme, Inc", "", "2021")),
        ("Engineer | Acme | Pune | 2021", ("Engineer", "Acme", "Pune", "2021")),
        (" | Pune University |  | 2025", ("", "Pune University", "", "2025")),
        ("Engineer | New York, NY | 2021", ("Engineer", "", "New York, NY", "2021")),
        ("CareerCraft | Python, FastAPI | 2024", ("CareerCraft", "Python, FastAPI", "", "2024")),
    ],
)
def test_split_heading_positional(text, expected):
    p = split_heading(text)
    assert (p.role, p.employer, p.location, p.start) == expected


def test_format_heading_keeps_empty_inner_slots():
    assert (
        format_heading(EntryParts(role="Engineer", location="Remote", start="2021", end="2022"))
        == "### Engineer |  | Remote | 2021 - 2022"
    )
    assert format_heading(EntryParts(role="Engineer", employer="Acme")) == "### Engineer | Acme"
    assert format_heading(EntryParts(role="Engineer", start="2021")) == (
        "### Engineer |  |  | 2021"
    )


@pytest.mark.parametrize(
    "parts",
    [
        EntryParts("Engineer", "Acme", "Pune, India", "Jan 2021", "Present"),
        EntryParts("Engineer", "", "Remote", "2021", "2022"),
        EntryParts("Engineer", "Acme", "", "2021", ""),
        EntryParts("Engineer", "", "", "May 2023", ""),
        EntryParts("Engineer", "", "Pune, India", "", ""),
        EntryParts("Engineer", "Acme", "Pune", "", ""),
        EntryParts("", "Pune University", "", "2021", "2025"),
    ],
)
def test_format_split_round_trip(parts):
    assert split_heading(format_heading(parts)[4:]) == parts


def test_clearing_employer_keeps_location_slot():
    text = _exp("Engineer | Acme | Pune | 2021 - 2022")
    out = apply_fixes(text, experience=[{"index": 0, "employer": ""}])
    assert "### Engineer |  | Pune | 2021 - 2022" in out
    [entry] = review_resume(out)["experience"]
    assert (entry["employer"], entry["location"]) == ("", "Pune")
    assert "missing_employer" in entry["issues"]


# 8. only real date ranges are dates


@pytest.mark.parametrize(
    "text,employer,location",
    [
        ("Intern | Deloitte (Summer 2023)", "Deloitte (Summer 2023)", ""),
        ("Data Analyst | Know Now Inc", "Know Now Inc", ""),
        ("Winner | Smart India Hackathon 2022", "Smart India Hackathon 2022", ""),
    ],
)
def test_text_with_years_is_not_a_date_part(text, employer, location):
    p = split_heading(text)
    assert (p.employer, p.location, p.start, p.end) == (employer, location, "", "")


@pytest.mark.parametrize(
    "text,ok",
    [
        ("Jun 2019 – Mar 2021", True),
        ("2021-2024", True),
        ("2020 to 2022", True),
        ("06/2021 - 08/2022", True),
        ("May 2023", True),
        ("Summer 2023", True),
        ("Sept. 2020 — Present", True),
        ("January 2020 - Current", True),
        ("Deloitte (Summer 2023)", False),
        ("Know Now Inc", False),
        ("Smart India Hackathon 2022", False),
        ("Summer", False),
        ("", False),
    ],
)
def test_is_date_range(text, ok):
    assert is_date_range(text) is ok


@pytest.mark.parametrize(
    "value,start,end",
    [
        ("Jun 2019 – Mar 2021", "Jun 2019", "Mar 2021"),
        ("2021-2024", "2021", "2024"),
        ("2020 to 2022", "2020", "2022"),
        ("06/2021 - 08/2022", "06/2021", "08/2022"),
        ("May 2023", "May 2023", ""),
        ("Jan 2021 - Present", "Jan 2021", "Present"),
    ],
)
def test_split_dates(value, start, end):
    assert split_dates(value) == (start, end)


# 9. education without `###` and bold-pipe entries

EDU_PLAIN = """# Jane
jane@x.com | +1 555 010 0199
## EXPERIENCE
### Engineer | Acme | Pune | 2021 - 2022
- Built things
## EDUCATION
**B.Tech, CS** - IIT Bombay (2015 - 2019)
"""


def test_education_section_without_entries_counts():
    review = review_resume(EDU_PLAIN)
    assert review["issues"] == []
    assert review["has_education_section"] is True
    facts = {"education": [{"degree": "B.Tech", "institution": "IIT Bombay", "end": "2019"}]}
    assert apply_saved_facts(EDU_PLAIN, facts) == EDU_PLAIN


def test_bold_pipe_lines_are_entries():
    text = (
        "# Jane\n## EXPERIENCE\n**Engineer** | Acme | 2021 - 2022\n- Built things\n"
        "## EDUCATION\n**B.Tech** | IIT Bombay | 2019\n"
    )
    review = review_resume(text)
    [exp] = review["experience"]
    assert (exp["role"], exp["employer"], exp["start"], exp["end"]) == (
        "Engineer",
        "Acme",
        "2021",
        "2022",
    )
    assert review["education"][0]["employer"] == "IIT Bombay"
    out = apply_fixes(text, experience=[{"index": 0, "location": "Pune"}])
    assert "### Engineer | Acme | Pune | 2021 - 2022" in out
    assert "**Engineer** | Acme" not in out


# 10. several fixes for the same entry merge


def test_fixes_for_same_index_merge():
    out = apply_fixes(
        SPARSE,
        experience=[
            {"index": 0, "start": "2020", "end": "2021"},
            {"index": 0, "location": "Pune", "start": None},
        ],
    )
    [entry] = review_resume(out)["experience"]
    assert (entry["location"], entry["start"], entry["end"]) == ("Pune", "2020", "2021")


def test_later_fix_keys_win():
    out = apply_fixes(
        SPARSE,
        experience=[
            {"index": 0, "start": "2020"},
            {"index": 0, "start": "2019"},
        ],
    )
    assert review_resume(out)["experience"][0]["start"] == "2019"


# 11. validation and injection


def test_unknown_education_index_raises_before_any_change():
    with pytest.raises(ValueError):
        apply_fixes(
            SPARSE,
            experience=[{"index": 0, "start": "2020"}],
            education=[{"index": 0, "degree": "B.Tech"}],
        )


def test_contact_values_cannot_inject_headings():
    out = apply_fixes(SPARSE, contact={"email": "a@b.com\n## HACK", "location": "# Pune\n### x"})
    assert len(_heading_lines(out)) == len(_heading_lines(SPARSE))


def test_name_values_cannot_inject_headings():
    out = apply_fixes("## SKILLS\nPython\n", full_name="Jane\n## HACK")
    assert _heading_lines(out) == ["# Jane ## HACK", "## SKILLS"]


# ── Regression tests for the second-review findings ─────────────────────────

# D1. legacy heading location heuristic


@pytest.mark.parametrize(
    "text,employer,location",
    [
        (
            "Engineer | Tata Consultancy Services, Mumbai | 2020 - 2021",
            "Tata Consultancy Services, Mumbai",
            "",
        ),
        ("Engineer | TechCorp, Bangalore | 2021 - 2022", "TechCorp, Bangalore", ""),
        ("Engineer | Infosys, Bangalore", "Infosys, Bangalore", ""),
        ("Engineer | Johnson, Matthey", "Johnson, Matthey", ""),
        ("Engineer | Pune, India | 2021 - 2022", "", "Pune, India"),
        ("Engineer | Remote | 2021 - 2022", "", "Remote"),
        ("Engineer | Remote", "", "Remote"),
        ("Engineer | work from HOME", "", "work from HOME"),
        ("Engineer | Seattle, WA | 2021", "", "Seattle, WA"),
        ("Engineer | Bengaluru,  karnataka  | 2021", "", "Bengaluru,  karnataka"),
        # A known region still needs a date part; a lowercase code is not a code.
        ("Engineer | Pune, India", "Pune, India", ""),
        ("Engineer | Seattle, wa | 2021", "Seattle, wa", ""),
        ("Engineer | Acme | Pune, India | 2021", "Acme", "Pune, India"),
    ],
)
def test_d1_legacy_heading_location(text, employer, location):
    p = split_heading(text)
    assert (p.role, p.employer, p.location) == ("Engineer", employer, location)


def test_d1_empty_slot_headings_stay_positional():
    p = split_heading("Engineer |  | Tata Consultancy Services, Mumbai | 2021")
    assert (p.employer, p.location) == ("", "Tata Consultancy Services, Mumbai")
    p = split_heading("Engineer | Remote |  | 2021")
    assert (p.employer, p.location) == ("Remote", "")


def test_d1_adding_dates_keeps_employer_with_city():
    text = _exp("Engineer | Tata Consultancy Services, Mumbai")
    assert "missing_employer" not in _codes(review_resume(text))
    out = apply_fixes(text, experience=[{"index": 0, "start": "2020", "end": "2021"}])
    assert "### Engineer | Tata Consultancy Services, Mumbai |  | 2020 - 2021" in out
    [entry] = review_resume(out)["experience"]
    assert entry["employer"] == "Tata Consultancy Services, Mumbai"
    assert entry["issues"] == []


# D2. date grammar


@pytest.mark.parametrize(
    "text",
    [
        "Jan 2021 - Dec 2022",
        "2021-2024",
        "2021-22",
        "2021 – 22",
        "Q1 2021 - Q3 2022",
        "Since 2021",
        "From Jan 2021",
        "2020 - Mid 2021",
        "Mid-2021 - 2023",
        "Early 2020 – Late 2021",
        "01.2021 - 03.2022",
        "06/2021 - 08/2022",
        "06-2021 - 08-2022",
        "2020 to date",
        "Summer 2023",
        "May 2023",
        "Sept. 2020 — Now",
        "Jan 2021 - Ongoing",
    ],
)
def test_d2_valid_date_ranges(text):
    assert is_date_range(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Deloitte (Summer 2023)",
        "Smart India Hackathon 2022",
        "Know Now Inc",
        "Remote",
        "Summer",
        "22",
        "2021 22",
        "Jan 22",
        "Mid",
        "Mid Jan",
        "2021 Since",
        "2021 date",
        "Q5 2021",
        "Mayfair 2021",
    ],
)
def test_d2_invalid_date_ranges(text):
    assert is_date_range(text) is False


@pytest.mark.parametrize(
    "value,start,end",
    [
        ("2021-22", "2021", "22"),
        ("2021 – 22", "2021", "22"),
        ("Mid-2021 - 2023", "Mid-2021", "2023"),
        ("Mid-2021", "Mid-2021", ""),
        ("06-2021", "06-2021", ""),
        ("Since 2021", "Since 2021", ""),
        ("2020 to date", "2020", "Present"),
        ("2020 - Mid 2021", "2020", "Mid 2021"),
        ("Q1 2021 - Q3 2022", "Q1 2021", "Q3 2022"),
        ("01.2021 - 03.2022", "01.2021", "03.2022"),
        ("2021-Present", "2021", "Present"),
    ],
)
def test_d2_split_dates(value, start, end):
    assert split_dates(value) == (start, end)


def test_d2_mid_year_heading_is_dated():
    p = split_heading("Engineer | Acme | Mid-2021 - 2023")
    assert (p.employer, p.location, p.start, p.end) == ("Acme", "", "Mid-2021", "2023")


# 3. unlabeled contact parts are a location only when place-like


def test_unlabeled_title_is_not_a_contact_location():
    text = "# Jane\nML Engineer | jane@x.com | +91 98765 43210\n## SKILLS\nPython\n"
    contact = parse_contact(text)
    assert (contact["location"], contact["email"]) == ("", "jane@x.com")
    out = ensure_contact(text, {"location": "Pune, India"})
    assert "ML Engineer | jane@x.com | +91 98765 43210 | Pune, India" in out
    assert parse_contact(out)["location"] == "Pune, India"


def test_unclassified_contact_value_is_not_appended_twice():
    text = "# Jane\njane@x.com\n## SKILLS\nPython\n"
    once = apply_fixes(text, contact={"location": "Pune"})
    assert "jane@x.com | Pune" in once
    assert apply_fixes(once, contact={"location": "Pune"}) == once


@pytest.mark.parametrize(
    "line,location",
    [
        ("Open to relocation | jane@x.com", ""),
        ("Location: Pune | jane@x.com", "Pune"),
        ("jane@x.com | Sector 62, Noida", "Sector 62, Noida"),
        ("jane@x.com | Remote", "Remote"),
    ],
)
def test_contact_location_classification(line, location):
    assert parse_contact(f"# Jane\n{line}\n## SKILLS\nPython\n")["location"] == location


# 4. Markdown-link contact parts

LINKED = (
    "# Jane\n[jane@x.com](mailto:jane@x.com) | [LinkedIn](https://linkedin.com/in/j) | "
    "[+91 98765 43210](tel:+919876543210)\n## SKILLS\nPython\n"
)


def test_markdown_link_contact_parts_are_classified():
    contact = parse_contact(LINKED)
    assert (contact["email"], contact["linkedin"], contact["phone"]) == (
        "jane@x.com",
        "https://linkedin.com/in/j",
        "+91 98765 43210",
    )
    mailto_only = "# Jane\n[Email me](mailto:jane@x.com?subject=Hi)\n## SKILLS\nPython\n"
    assert parse_contact(mailto_only)["email"] == "jane@x.com"


def test_ensure_contact_with_markdown_links_adds_no_second_line():
    out = ensure_contact(LINKED, {"email": "jane@x.com", "location": "Pune, India"})
    lines = out.splitlines()
    assert lines[1] == (
        "[jane@x.com](mailto:jane@x.com) | [LinkedIn](https://linkedin.com/in/j) | "
        "[+91 98765 43210](tel:+919876543210) | Pune, India"
    )
    assert out.count("jane@x.com") == 2  # once as text, once in the mailto target
    assert ensure_contact(LINKED, {"email": "other@x.com"}) == LINKED


def test_markdown_link_part_rewritten_only_when_changed():
    out = apply_fixes(LINKED, contact={"phone": "+91 90000 00000", "email": "jane@x.com"})
    assert _line_with(out, "mailto") == (
        "[jane@x.com](mailto:jane@x.com) | [LinkedIn](https://linkedin.com/in/j) | "
        "+91 90000 00000"
    )


# 5. warning filter is specific about employer and dates


@pytest.mark.parametrize(
    "warning",
    [
        "Missing: Terraform, Kubernetes (no employer has used these)",
        "Missing dates for Kafka projects",
        "No project dates are given for the hackathon entries.",
        "No employer has used Terraform in production.",
    ],
)
def test_unrelated_employer_and_date_mentions_are_kept(warning):
    review = review_resume(FULL)
    assert review["issues"] == []
    assert filter_resolved_warnings([warning], review) == [warning]


@pytest.mark.parametrize(
    "warning",
    [
        "The employer name for the internship is missing.",
        "Missing employer name for the Prompt Engineer Intern role.",
        "The employer line is cut off.",
        "Internship dates are missing.",
        "Missing start date for the Prompt Engineer Intern role.",
        "No duration is given for the role.",
        "Education dates were not provided.",
    ],
)
def test_resolved_employer_and_date_warnings_are_dropped(warning):
    assert filter_resolved_warnings([warning], review_resume(FULL)) == []
    assert filter_resolved_warnings([warning], review_resume(SPARSE)) == [warning]


# 6. header placeholder lines and prose spacing


@pytest.mark.parametrize("line", ["N/A", "tbd", "- NOT_PROVIDED", "[n/a]"])
def test_clean_placeholders_drops_header_placeholder_lines(line):
    out = clean_placeholders(f"# Jane\n{line}\n## SUMMARY\nN/A\n")
    assert out == "# Jane\n## SUMMARY\nN/A\n"


def test_clean_placeholders_collapses_space_left_by_inline_token():
    out = clean_placeholders("# Jane\nContact details NOT_PROVIDED by candidate.\n## SKILLS\nPy\n")
    assert "Contact details by candidate." in out.splitlines()
