"""ATS-safe resume PDFs rendered from the Resume Agent's Markdown.

Layout rules follow current ATS guidance (Jobscan, ResumeAdapter, OwlApply
2026 checklists): one column; a standard core font (Helvetica ≈ Arial, or
Times) at 10-11 pt; 0.5-0.75 in margins; standard uppercase section
headings; contact details as body text (never a header/footer); plain round
bullets; dates on the role line in one consistent format; no tables, text
boxes, icons, images or skill bars. Every line is real, selectable text drawn
top-to-bottom, left-to-right, so extraction order equals reading order.

The three templates differ in typography, not structure, so all three parse
identically:

- modern     — Helvetica, centered navy header, accent rules under headings
- classic    — Times, centered black-and-white, conservative (Taleo-safe)
- technical  — Helvetica, compact left-aligned header, teal accents, denser
               spacing so skills and projects fit on one page
"""

import io
import re
import unicodedata
from dataclasses import dataclass
from html import escape
from typing import Literal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable, HRFlowable, Paragraph, SimpleDocTemplate

from app.services.resume_structure import clean_placeholders, split_heading

Template = Literal["classic", "modern", "technical"]

_SECTIONS = {
    "summary", "professional summary", "profile", "objective", "experience",
    "work experience", "professional experience", "employment", "work history",
    "education", "skills", "technical skills", "technologies", "projects",
    "certifications", "awards", "publications", "languages", "volunteer experience",
    "internships", "achievements", "core competencies",
}
_BULLET = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
_HEADING = re.compile(r"^(#{1,6})\s+")
_LIST_SEPARATORS = re.compile(r"[,;|/]")
_DATE = re.compile(r"\b(?:19|20)\d{2}\b|\b(?:present|current)\b", re.I)
_CONTACT = re.compile(r"@|(?:\+?\d[\d\s().-]{7,})|(?:linkedin|github)\.com|https?://", re.I)


@dataclass(frozen=True)
class Theme:
    regular: str
    bold: str
    italic: str
    ink: str             # name + heading color
    text: str            # body color
    muted: str           # contact / dates color
    header_align: int
    name_size: float
    heading_size: float
    body_size: float
    leading: float       # body leading multiplier
    margin_x: float      # inches
    margin_y: float
    section_gap: float   # points before each section heading
    heading_rule: float  # rule thickness under headings (0 = none)


THEMES: dict[str, Theme] = {
    "modern": Theme(
        regular="Helvetica", bold="Helvetica-Bold", italic="Helvetica-Oblique",
        ink="#1F3A5F", text="#1A1A1A", muted="#4A5563", header_align=TA_CENTER,
        name_size=22, heading_size=11, body_size=10, leading=1.32,
        margin_x=0.65, margin_y=0.55, section_gap=10, heading_rule=0.8,
    ),
    "classic": Theme(
        regular="Times-Roman", bold="Times-Bold", italic="Times-Italic",
        ink="#000000", text="#000000", muted="#222222", header_align=TA_CENTER,
        name_size=20, heading_size=11.5, body_size=10.8, leading=1.25,
        margin_x=0.75, margin_y=0.6, section_gap=9, heading_rule=0.6,
    ),
    "technical": Theme(
        regular="Helvetica", bold="Helvetica-Bold", italic="Helvetica-Oblique",
        ink="#0F5C63", text="#1A1A1A", muted="#46525A", header_align=TA_LEFT,
        name_size=19, heading_size=10.5, body_size=9.6, leading=1.28,
        margin_x=0.55, margin_y=0.5, section_gap=8, heading_rule=0.6,
    ),
}

_ASCII_PUNCT = str.maketrans({
    "–": "-", "—": "-", "−": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
    "\u00a0": " ", "\u2009": " ", "\u200b": "",
})


def _winansi(value: str) -> str:
    """Core PDF fonts use WinAnsi; fold anything outside it to ASCII.

    Unencodable characters would otherwise render as blank glyphs, which is
    worse for an ATS than a transliteration.
    """
    out = []
    for ch in value:
        try:
            ch.encode("cp1252")
            out.append(ch)
        except UnicodeEncodeError:
            out.append(unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode())
    return "".join(out)


def _markup(value: str) -> str:
    """Keep basic Markdown emphasis while escaping all model-supplied text."""
    value = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r"\1 (\2)", value)
    value = _winansi(value.translate(_ASCII_PUNCT))
    value = escape(value.replace("`", ""), quote=False)
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value).replace("**", "")
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", value)


def _plain(value: str) -> str:
    return re.sub(r"[*_`]", "", value).strip()


def _dates(value: str) -> str:
    """One consistent range separator: an en dash with spaces."""
    return re.sub(r"\s*-\s*", " \u2013 ", _markup(value))


class _SplitRow(Flowable):
    """Left text with right-aligned text on the same first line.

    Replaces a two-cell table: the output is two ordinary text runs, drawn
    left then right, which every ATS extracts in reading order.
    """

    def __init__(
        self, left: Paragraph, right: Paragraph | None, right_text: str, font: str, size: float,
    ):
        super().__init__()
        self.left = left
        self.right = right
        self._natural = stringWidth(right_text, font, size) + 2 if right is not None else 0

    def wrap(self, avail_width, avail_height):
        self._rw = min(self._natural, avail_width * 0.42)
        self._lw = avail_width - self._rw - (10 if self._rw else 0)
        _, self._lh = self.left.wrap(self._lw, avail_height)
        self._rh = self.right.wrap(self._rw, avail_height)[1] if self.right is not None else 0
        self.width, self.height = avail_width, max(self._lh, self._rh)
        return self.width, self.height

    def draw(self):
        self.left.drawOn(self.canv, 0, self.height - self._lh)
        if self.right is not None:
            self.right.drawOn(self.canv, self.width - self._rw, self.height - self._rh)


class _Styles:
    def __init__(self, t: Theme):
        ink, text, muted = (colors.HexColor(c) for c in (t.ink, t.text, t.muted))
        body_leading = t.body_size * t.leading
        self.name = ParagraphStyle(
            "ResumeName", fontName=t.bold, fontSize=t.name_size,
            leading=t.name_size * 1.15, alignment=t.header_align, textColor=ink, spaceAfter=3,
        )
        self.headline = ParagraphStyle(
            "ResumeHeadline", fontName=t.regular, fontSize=t.body_size + 1,
            leading=(t.body_size + 1) * 1.3, alignment=t.header_align, textColor=text, spaceAfter=1,
        )
        self.contact = ParagraphStyle(
            "ResumeContact", fontName=t.regular, fontSize=t.body_size - 0.6,
            leading=t.body_size * 1.35, alignment=t.header_align, textColor=muted, spaceAfter=1,
        )
        self.section = ParagraphStyle(
            "ResumeSection", fontName=t.bold, fontSize=t.heading_size,
            leading=t.heading_size * 1.25, textColor=ink, spaceBefore=t.section_gap,
            spaceAfter=2, keepWithNext=True,
        )
        self.role = ParagraphStyle(
            "ResumeRole", fontName=t.bold, fontSize=t.body_size + 0.4,
            leading=(t.body_size + 0.4) * 1.3, textColor=text,
        )
        self.org = ParagraphStyle(
            "ResumeOrg", fontName=t.italic, fontSize=t.body_size,
            leading=body_leading, textColor=text,
        )
        self.right = ParagraphStyle(
            "ResumeDate", fontName=t.regular, fontSize=t.body_size - 0.4,
            leading=(t.body_size + 0.4) * 1.3, alignment=TA_RIGHT, textColor=muted,
        )
        self.right_italic = ParagraphStyle(
            "ResumeLocation", parent=self.right, fontName=t.italic, leading=body_leading,
        )
        self.body = ParagraphStyle(
            "ResumeBody", fontName=t.regular, fontSize=t.body_size,
            leading=body_leading, textColor=text, spaceAfter=2,
        )
        self.bullet = ParagraphStyle(
            "ResumeBullet", parent=self.body, leftIndent=12, bulletIndent=2,
            bulletFontName=t.regular, bulletFontSize=t.body_size, spaceAfter=1.2,
        )


def _entry_rows(line: str, theme: Theme, st: _Styles) -> list[Flowable]:
    """`Role | Employer | Location | Dates` → two rows:

        **Role**                                   Jan 2023 – Present
        *Employer*                                           Location
    """
    parts = split_heading(line)
    if not (parts.role or parts.employer):
        return [Paragraph(_markup(_plain(line)), st.role)]
    rows: list[Flowable] = []
    dates = parts.dates
    top = _SplitRow(
        Paragraph(_markup(parts.role or parts.employer), st.role),
        Paragraph(_dates(dates), st.right) if dates else None,
        _plain(_dates(dates)).replace("&amp;", "&"), theme.regular, theme.body_size - 0.4,
    )
    top.spaceBefore = 5
    top.keepWithNext = True
    rows.append(top)
    employer = parts.employer if parts.role else ""
    if employer or parts.location:
        second = _SplitRow(
            Paragraph(_markup(employer), st.org),
            Paragraph(_markup(parts.location), st.right_italic) if parts.location else None,
            parts.location, theme.italic, theme.body_size - 0.4,
        )
        second.spaceAfter = 1.5
        second.keepWithNext = True
        rows.append(second)
    return rows


def generate_resume_pdf(
    resume_text: str,
    full_name: str = "",
    template: Template = "modern",
) -> bytes:
    if not resume_text or not resume_text.strip():
        raise ValueError("resume_text cannot be empty")
    if template not in THEMES:
        raise ValueError(f"Unknown resume template: {template}")
    cleaned = clean_placeholders(resume_text)
    if not cleaned.strip():
        raise ValueError("resume_text cannot be empty")

    theme = THEMES[template]
    st = _Styles(theme)
    ink = colors.HexColor(theme.ink)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=theme.margin_x * inch, rightMargin=theme.margin_x * inch,
        topMargin=theme.margin_y * inch, bottomMargin=theme.margin_y * inch,
        title=f"{full_name or 'Resume'} - Resume", author=full_name or "",
        subject="Resume", creator="CareerCraft AI",
    )
    story: list[Flowable] = []
    first_line = True
    in_header = True
    lines = cleaned.strip().splitlines()
    # Markdown resumes mark sections with `##`; only plain-text resumes need the
    # all-caps heuristic, otherwise lines like "AWS, GCP, SQL" become headings.
    has_markdown_sections = any(_HEADING.match(raw.strip()) for raw in lines)

    for raw in lines:
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
            story.append(Paragraph(_markup(name), st.name))
            first_line = False
            if plain.casefold() == name.casefold() or (level == 1 and full_name):
                continue

        section = plain.rstrip(":")
        caps_heading = (
            not has_markdown_sections
            and section.isupper()
            and 2 < len(section) < 40
            and not _LIST_SEPARATORS.search(section)
        )
        if section.casefold() in _SECTIONS or (level == 2 and len(section) < 50) or caps_heading:
            in_header = False
            story.append(Paragraph(_markup(section.upper()), st.section))
            if theme.heading_rule:
                rule = HRFlowable(
                    width="100%", thickness=theme.heading_rule, color=ink,
                    spaceBefore=0, spaceAfter=4,
                )
                rule.keepWithNext = True
                story.append(rule)
            continue
        if in_header:
            if _CONTACT.search(plain):
                contact = " | ".join(p.strip() for p in re.split(r"\s*[|·•]\s*", line) if p.strip())
                story.append(Paragraph(_markup(contact), st.contact))
                continue
            if level == 0 and not _BULLET.match(line) and len(plain) < 90:
                story.append(Paragraph(_markup(line), st.headline))
                continue
        in_header = False

        bullet = _BULLET.match(line)
        if bullet:
            story.append(Paragraph(_markup(line[bullet.end():]), st.bullet, bulletText="\u2022"))
            continue
        is_entry = level >= 3 or (
            line.startswith("**") and "|" in line and _DATE.search(plain)
        )
        if is_entry:
            story.extend(_entry_rows(line, theme, st))
            continue
        story.append(Paragraph(_markup(line), st.body))

    doc.build(story)
    return buffer.getvalue()
