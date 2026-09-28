"""Single-column resume PDFs with readable Markdown headings and bullets."""

import io
import re
from html import escape
from pathlib import Path
from typing import Literal

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Table, TableStyle

_FONT_DIR = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("ResumeSans", str(_FONT_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("ResumeSansBold", str(_FONT_DIR / "VeraBd.ttf")))
pdfmetrics.registerFontFamily("ResumeSans", normal="ResumeSans", bold="ResumeSansBold")

Template = Literal["classic", "modern", "technical"]
_SECTIONS = {
    "summary", "professional summary", "profile", "objective", "experience",
    "work experience", "professional experience", "employment", "work history",
    "education", "skills", "technical skills", "technologies", "projects",
    "certifications", "awards", "publications", "languages", "volunteer experience",
}
_BULLET = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
_HEADING = re.compile(r"^(#{1,6})\s+")
_DATE = re.compile(r"\b(?:19|20)\d{2}\b|\b(?:present|current)\b", re.I)
_CONTACT = re.compile(r"@|(?:\+?\d[\d\s().-]{7,})|(?:linkedin|github)\.com|https?://", re.I)
_THEMES = {
    "classic": ("ResumeSans", "ResumeSansBold", "#202020", TA_LEFT, 20, 10),
    "modern": ("ResumeSans", "ResumeSansBold", "#243B53", TA_CENTER, 21, 10),
    "technical": ("ResumeSans", "ResumeSansBold", "#145A66", TA_LEFT, 20, 9.7),
}


def _markup(value: str) -> str:
    """Keep basic Markdown emphasis while escaping all model supplied text."""
    value = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r"\1 (\2)", value)
    value = value.translate(str.maketrans({
        "–": "-", "—": "-", "−": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
    }))
    value = escape(value.replace("`", ""), quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value).replace("**", "")


def _plain(value: str) -> str:
    return re.sub(r"[*_`]", "", value).strip()


def generate_resume_pdf(
    resume_text: str,
    full_name: str = "",
    template: Template = "modern",
) -> bytes:
    if not resume_text or not resume_text.strip():
        raise ValueError("resume_text cannot be empty")
    if template not in _THEMES:
        raise ValueError(f"Unknown resume template: {template}")

    regular, bold, accent, alignment, name_size, body_size = _THEMES[template]
    ink = colors.HexColor(accent)
    name_style = ParagraphStyle(
        "ResumeName", fontName=bold, fontSize=name_size, leading=name_size + 3,
        alignment=alignment, textColor=ink, spaceAfter=4,
    )
    contact_style = ParagraphStyle(
        "ResumeContact", fontName=regular, fontSize=8.6, leading=12,
        alignment=alignment, textColor=colors.HexColor("#454B54"), spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "ResumeSection", fontName=bold, fontSize=9.4, leading=12,
        textColor=ink, spaceBefore=11, spaceAfter=3, keepWithNext=True,
    )
    entry_style = ParagraphStyle(
        "ResumeEntry", fontName=bold, fontSize=body_size, leading=13,
        textColor=colors.HexColor("#202020"), spaceBefore=5, spaceAfter=2,
        keepWithNext=True,
    )
    date_style = ParagraphStyle(
        "ResumeDate", fontName=regular, fontSize=8.8, leading=13,
        alignment=TA_RIGHT, textColor=colors.HexColor("#454B54"),
    )
    body_style = ParagraphStyle(
        "ResumeBody", fontName=regular, fontSize=body_size,
        leading=body_size + 3.2, spaceAfter=3,
    )
    bullet_style = ParagraphStyle(
        "ResumeBullet", parent=body_style, leftIndent=13,
        bulletIndent=2, spaceAfter=2,
    )
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, leftMargin=0.7 * inch,
        rightMargin=0.7 * inch, topMargin=0.58 * inch,
        bottomMargin=0.62 * inch, title=f"{full_name or 'Resume'} - Resume",
    )
    story = []
    first_line = True
    in_header = True

    for raw in resume_text.strip().splitlines():
        line = raw.strip()
        if not line or line in {"---", "***", "___"}:
            continue
        heading = _HEADING.match(line)
        level = len(heading.group(1)) if heading else 0
        if heading:
            line = line[heading.end():].strip()
        if not line:
            continue
        plain = _plain(line)
        if first_line:
            name = full_name.strip() or plain
            story.append(Paragraph(_markup(name), name_style))
            first_line = False
            if plain.casefold() == name.casefold() or (level == 1 and full_name):
                continue

        section = plain.rstrip(":")
        if (section.casefold() in _SECTIONS or
                (level == 2 and len(section) < 50) or
                (section.isupper() and 2 < len(section) < 40)):
            in_header = False
            story.append(Paragraph(_markup(section.upper()), section_style))
            rule = HRFlowable(width="100%", thickness=0.65, color=ink, spaceAfter=5)
            rule.keepWithNext = True
            story.append(rule)
            continue
        if in_header and _CONTACT.search(plain):
            story.append(Paragraph(_markup(line), contact_style))
            continue
        in_header = False

        bullet = _BULLET.match(line)
        if bullet:
            story.append(Paragraph(_markup(line[bullet.end():]), bullet_style, bulletText="-"))
            continue
        is_entry = level >= 3 or (
            line.startswith("**") and
            (_DATE.search(plain) or "|" in line)
        )
        if is_entry:
            parts = [part.strip() for part in line.split("|")]
            if len(parts) > 1 and _DATE.search(_plain(parts[-1])):
                left = " | ".join(parts[:-1])
                row = Table(
                    [[Paragraph(_markup(left), entry_style),
                      Paragraph(_markup(parts[-1]), date_style)]],
                    colWidths=[doc.width - 1.55 * inch, 1.55 * inch],
                    hAlign="LEFT",
                )
                row.setStyle(TableStyle([
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                row.keepWithNext = True
                story.append(row)
            else:
                story.append(Paragraph(_markup(line), entry_style))
            continue
        story.append(Paragraph(_markup(line), body_style))

    doc.build(story)
    return buffer.getvalue()
