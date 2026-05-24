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
