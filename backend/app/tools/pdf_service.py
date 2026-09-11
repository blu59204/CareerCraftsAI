"""
pdf_service.py — PDF resume generation and Supabase Storage upload.

Generates ATS-friendly PDF resumes using ReportLab and uploads them
to Supabase Storage for download in the frontend.
"""
from __future__ import annotations

import io
import uuid

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, ListFlowable, ListItem

from app.services.storage_service import upload_file

BUCKET = "user-documents"
SECTION_HEADER_STYLE = ParagraphStyle(
    "SectionHeader",
    fontSize=12,
    leading=16,
    spaceAfter=6,
    spaceBefore=12,
    fontName="Helvetica-Bold",
)
BODY_STYLE = ParagraphStyle(
    "Body",
    fontSize=10,
    leading=14,
    spaceAfter=4,
    fontName="Helvetica",
)
BULLET_STYLE = ParagraphStyle(
    "Bullet",
    fontSize=10,
    leading=14,
    spaceAfter=2,
    fontName="Helvetica",
    leftIndent=20,
    bulletIndent=10,
)


class PDFService:
    """Generate ATS-friendly PDF resumes from structured text."""

    def generate(self, resume_text: str) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=inch,
            rightMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )

        story: list = []
        sections = self._parse_sections(resume_text)

        for title, content in sections:
            story.append(Paragraph(title, SECTION_HEADER_STYLE))

            if title.lower() in ("experience", "projects", "achievements"):
                bullets = self._extract_bullets(content)
                if bullets:
                    list_items = [ListItem(Paragraph(b, BULLET_STYLE)) for b in bullets]
                    story.append(ListFlowable(list_items, bulletType="bullet", bulletFontName="Helvetica"))
                else:
                    story.append(Paragraph(content, BODY_STYLE))
            else:
                story.append(Paragraph(content, BODY_STYLE))

            story.append(Spacer(1, 6))

        doc.build(story)
        return buf.getvalue()

    def _parse_sections(self, text: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        lines = text.split("\n")
        current_title = "Summary"
        current_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.isupper() or stripped.endswith(":") or (
                len(stripped) < 50 and not stripped.endswith(".") and
                all(not c.islower() or c.isupper() for c in stripped if c.isalpha())
            ):
                if current_lines:
                    sections.append((current_title, "\n".join(current_lines)))
                current_title = stripped.strip(":").strip()
                current_lines = []
            else:
                current_lines.append(stripped)

        if current_lines:
            sections.append((current_title, "\n".join(current_lines)))

        return sections if sections else [("Resume", text)]

    def _extract_bullets(self, text: str) -> list[str]:
        bullets: list[str] = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith(("- ", "• ", "* ", "· ")):
                bullets.append(stripped[2:].strip())
            elif stripped and len(stripped) < 200:
                bullets.append(stripped)
        return bullets if bullets else []


async def upload_to_supabase_storage(pdf_bytes: bytes, user_id: str, run_id: str) -> str:
    path = upload_file(
        user_id=user_id,
        filename="resume.pdf",
        content=pdf_bytes,
        content_type="application/pdf",
    )
    return path
