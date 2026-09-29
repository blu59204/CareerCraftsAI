import fitz  # PyMuPDF
import pytest

from app.services.pdf_service import THEMES, generate_resume_pdf

TEMPLATES = ["modern", "classic", "technical"]


def test_generate_pdf_returns_bytes():
    resume_text = """John Doe
john@example.com | +1-555-0100

EXPERIENCE
Senior Engineer, Acme Corp (2020-2024)
- Led backend rewrite to FastAPI, cut p99 latency 40%

EDUCATION
B.S. Computer Science, State University (2019)

SKILLS
Python, FastAPI, PostgreSQL, Docker"""
    pdf_bytes = generate_resume_pdf(resume_text, full_name="John Doe")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_pdf_with_empty_text_raises():
    with pytest.raises(ValueError, match="resume_text cannot be empty"):
        generate_resume_pdf("", full_name="Test User")


def test_placeholder_only_text_raises():
    with pytest.raises(ValueError, match="resume_text cannot be empty"):
        generate_resume_pdf("NOT_PROVIDED", full_name="Test User")


def test_unknown_template_raises():
    with pytest.raises(ValueError, match="Unknown resume template"):
        generate_resume_pdf("# Jane\n## SKILLS\nPython", template="fancy")  # type: ignore[arg-type]


# ── Layout helpers ──────────────────────────────────────────────────────────

def _lines(pdf: bytes) -> list[tuple[str, float, str]]:
    """(font, size, text) for each rendered line, using the line's last span
    so a bullet glyph span does not mask the body text."""
    out = []
    for block in fitz.open(stream=pdf, filetype="pdf")[0].get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            span = line["spans"][-1]
            text = "".join(s["text"] for s in line["spans"]).strip()
            out.append((span["font"], round(span["size"], 1), text))
    return out


def _headings(pdf: bytes, template: str) -> list[str]:
    size = round(THEMES[template].heading_size, 1)
    return [text for font, s, text in _lines(pdf) if s == size and "Bold" in font]


MARKDOWN_RESUME = """# Jane Doe
jane@example.com | +91 98765 43210 | linkedin.com/in/jane
## SKILLS
AWS, GCP, SQL
## EXPERIENCE
### Backend Engineer | Acme | Pune, India | 2021 - Present
- Built APIs
"""


@pytest.mark.parametrize("template", TEMPLATES)
def test_all_caps_skill_line_is_not_a_heading(template):
    pdf = generate_resume_pdf(MARKDOWN_RESUME, full_name="Jane Doe", template=template)
    assert _headings(pdf, template) == ["SKILLS", "EXPERIENCE"]
    texts = [text for _, _, text in _lines(pdf)]
    assert "AWS, GCP, SQL" in texts


def test_plain_text_resume_still_detects_all_caps_headings():
    text = (
        "Jane Doe\njane@example.com\nMY OPEN SOURCE WORK\n"
        "Maintainer of a parser\nSKILLS\nGO, RUST"
    )
    pdf = generate_resume_pdf(text, template="classic")
    # Known section names and bare all-caps titles become headings; an
    # all-caps comma-separated list does not.
    assert _headings(pdf, "classic") == ["MY OPEN SOURCE WORK", "SKILLS"]


@pytest.mark.parametrize("template", TEMPLATES)
def test_entry_renders_role_dates_employer_location(template):
    pdf = generate_resume_pdf(MARKDOWN_RESUME, full_name="Jane Doe", template=template)
    lines = _lines(pdf)
    texts = [text for _, _, text in lines]
    assert texts[0] == "Jane Doe"
    assert texts.count("Jane Doe") == 1  # `# Jane Doe` is not repeated
    assert "jane@example.com | +91 98765 43210 | linkedin.com/in/jane" in texts
    # Row 1: bold role, right-aligned dates with an en dash.
    assert "Backend Engineer" in texts
    assert "2021 \u2013 Present" in texts
    # Row 2: italic employer, right-aligned location.
    fonts = {text: font for font, _, text in lines}
    assert "Bold" in fonts["Backend Engineer"]
    assert "Acme" in texts and ("Italic" in fonts["Acme"] or "Oblique" in fonts["Acme"])
    assert "Pune, India" in texts
    assert any(text.endswith("Built APIs") for text in texts)


def test_reading_order_is_top_to_bottom():
    pdf = generate_resume_pdf(MARKDOWN_RESUME, full_name="Jane Doe", template="modern")
    text = fitz.open(stream=pdf, filetype="pdf")[0].get_text()
    order = ["Jane Doe", "jane@example.com", "SKILLS", "EXPERIENCE", "Backend Engineer",
             "2021", "Acme", "Built APIs"]
    positions = [text.index(token) for token in order]
    assert positions == sorted(positions)


def test_templates_use_distinct_typography():
    fonts = {}
    for template in TEMPLATES:
        pdf = generate_resume_pdf(MARKDOWN_RESUME, full_name="Jane Doe", template=template)
        fonts[template] = {font for font, _, _ in _lines(pdf)}
    assert any("Times" in f for f in fonts["classic"])
    assert all("Helvetica" in f for f in fonts["modern"] | fonts["technical"])


def test_placeholders_never_reach_the_pdf():
    text = (
        "# Jane\n## EXPERIENCE\n### Intern | Acme | NOT_PROVIDED\n- Did work\n"
        "## EDUCATION\nNOT_PROVIDED\n"
    )
    pdf = generate_resume_pdf(text, full_name="Jane", template="modern")
    body = fitz.open(stream=pdf, filetype="pdf")[0].get_text()
    assert "NOT_PROVIDED" not in body
    assert "EDUCATION" not in body


def test_non_latin_characters_are_transliterated_not_dropped():
    text = "# Jane\n## SUMMARY\nBuilt Zürich café app → shipped ✓"
    pdf = generate_resume_pdf(text, full_name="Jane", template="modern")
    body = fitz.open(stream=pdf, filetype="pdf")[0].get_text()
    assert "Zürich café app" in body


def test_model_text_is_escaped_not_interpreted_as_markup():
    text = "# Jane\n## SUMMARY\nLoves <script>alert(1)</script> & **bold** claims"
    pdf = generate_resume_pdf(text, full_name="Jane", template="modern")
    body = " ".join(t for _, _, t in _lines(pdf))
    assert "<script>alert(1)</script> & bold claims" in body
