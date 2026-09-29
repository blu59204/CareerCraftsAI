"""Round-3 review: contact-line parsing, Markdown link parts, header placeholders."""

import pytest

from app.services.resume_structure import clean_placeholders, ensure_contact, parse_contact

# ── (a) unlabeled parts are locations only when place-like ─────────────────


def test_unlabeled_title_is_not_location():
    md = "# Jane Doe\nML Engineer | jane@x.com | +91 98765 43210\n\n## Experience\n"
    contact = parse_contact(md)
    assert contact["location"] == ""
    assert contact["email"] == "jane@x.com"
    assert contact["phone"] == "+91 98765 43210"


def test_ensure_contact_appends_location_once_and_keeps_title():
    md = "# Jane Doe\nML Engineer | jane@x.com | +91 98765 43210\n\n## Experience\n"
    out = ensure_contact(md, {"location": "Pune, India"})
    assert out.count("Pune, India") == 1
    assert "ML Engineer | jane@x.com | +91 98765 43210 | Pune, India" in out
    # Parsed back as location, so a second pass does not append it again.
    assert ensure_contact(out, {"location": "Pune, India"}) == out


def test_open_to_relocation_is_not_location():
    md = "# Jane Doe\nOpen to relocation | jane@x.com\n\n## Experience\n"
    assert parse_contact(md)["location"] == ""
    assert parse_contact(md)["email"] == "jane@x.com"


@pytest.mark.parametrize(
    "line, location",
    [
        ("jane@x.com | Location: Pune", "Pune"),
        ("Location: Pune", "Pune"),
        ("jane@x.com | Sector 62, Noida", "Sector 62, Noida"),
        ("jane@x.com | Remote", "Remote"),
    ],
)
def test_place_like_parts_are_locations(line, location):
    assert parse_contact(f"# Jane Doe\n{line}\n\n## Experience\n")["location"] == location


# ── (b) Markdown link parts ────────────────────────────────────────────────

_LINK_LINE = (
    "[jane@x.com](mailto:jane@x.com) | [LinkedIn](https://linkedin.com/in/j)"
    " | [+91 98765 43210](tel:+919876543210)"
)


def test_markdown_link_line_is_contact_line():
    contact = parse_contact(f"# Jane Doe\n{_LINK_LINE}\n\n## Experience\n")
    assert contact["email"] == "jane@x.com"
    assert contact["linkedin"] == "https://linkedin.com/in/j"
    assert contact["phone"] == "+91 98765 43210"


def test_ensure_contact_on_link_line_adds_no_second_line_or_duplicate():
    md = f"# Jane Doe\n{_LINK_LINE}\n\n## Experience\n"
    out = ensure_contact(
        md,
        {"email": "jane@x.com", "phone": "+91 98765 43210", "location": "Pune, India"},
    )
    lines = out.splitlines()
    assert lines[1] == f"{_LINK_LINE} | Pune, India"
    assert lines[2] == ""
    assert out.count("jane@x.com") == 2  # link text + mailto target only


def test_ensure_contact_link_line_already_complete_is_unchanged():
    md = f"# Jane Doe\n{_LINK_LINE}\n\n## Experience\n"
    assert ensure_contact(md, {"email": "jane@x.com", "linkedin": "linkedin.com/in/j"}) == md


# ── (c) header placeholder lines ───────────────────────────────────────────


@pytest.mark.parametrize("marker", ["N/A", "n/a", "TBD", "tbd", "NOT_PROVIDED", "not_provided"])
def test_header_placeholder_line_removed(marker):
    md = f"# Jane Doe\njane@x.com\n{marker}\n\n## Summary\nBuilt things.\n"
    out = clean_placeholders(md)
    assert marker not in out
    assert "jane@x.com" in out and "Built things." in out


def test_body_na_line_kept():
    md = "# Jane Doe\n\n## Skills\nN/A\n- Python\n"
    assert "N/A" in clean_placeholders(md)


def test_prose_marker_removed_without_double_space():
    md = "# Jane Doe\n\n## Summary\nContact details NOT_PROVIDED by candidate.\n"
    out = clean_placeholders(md)
    assert "Contact details by candidate." in out
    assert "NOT_PROVIDED" not in out and "  " not in out
