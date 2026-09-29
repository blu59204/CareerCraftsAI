import fitz  # PyMuPDF
import pytest

from app.services.pdf_service import generate_resume_pdf


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


def test_unknown_template_raises():
    with pytest.raises(ValueError, match="Unknown resume template"):
        generate_resume_pdf("# Jane\n## SKILLS\nPython", template="fancy")  # type: ignore[arg-type]


# ── Layout: which lines render as section headings ──────────────────────────

_SECTION_SIZE = 9.4  # ResumeSection fontSize in pdf_service


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


def _headings(pdf: bytes) -> list[str]:
    return [
        text for font, size, text in _lines(pdf)
        if size == _SECTION_SIZE and "Bold" in font
    ]


MARKDOWN_RESUME = """# Jane Doe
jane@example.com | +91 98765 43210 | linkedin.com/in/jane
## SKILLS
AWS, GCP, SQL
## EXPERIENCE
### Backend Engineer | Acme | 2021 - Present
- Built APIs
"""


@pytest.mark.parametrize("template", ["modern", "classic", "technical"])
def test_all_caps_skill_line_is_not_a_heading(template):
    pdf = generate_resume_pdf(MARKDOWN_RESUME, full_name="Jane Doe", template=template)
    assert _headings(pdf) == ["SKILLS", "EXPERIENCE"]
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
    assert _headings(pdf) == ["MY OPEN SOURCE WORK", "SKILLS"]


def test_name_contact_entry_and_bullet_rendering():
    pdf = generate_resume_pdf(MARKDOWN_RESUME, full_name="Jane Doe", template="modern")
    lines = _lines(pdf)
    texts = [text for _, _, text in lines]
    assert texts[0] == "Jane Doe"
    assert texts.count("Jane Doe") == 1  # `# Jane Doe` is not repeated
    assert "jane@example.com | +91 98765 43210 | linkedin.com/in/jane" in texts
    # The role line is split: title/employer left, dates in their own cell.
    assert "Backend Engineer | Acme" in texts
    assert "2021 - Present" in texts
    assert any(text.endswith("Built APIs") for text in texts)


def test_model_text_is_escaped_not_interpreted_as_markup():
    text = "# Jane\n## SUMMARY\nLoves <script>alert(1)</script> & **bold** claims"
    pdf = generate_resume_pdf(text, full_name="Jane", template="modern")
    body = " ".join(t for _, _, t in _lines(pdf))
    assert "<script>alert(1)</script> & bold claims" in body
