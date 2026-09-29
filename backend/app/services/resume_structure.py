"""Read, audit and patch the Markdown resumes the Resume Agent writes.

The agent emits a fixed shape (see agents/prompts/resume_prompt.py):

    # Full Name
    email | phone | City, Country | linkedin.com/in/you
    ## EXPERIENCE
    ### Role | Employer | Location | Mon YYYY - Mon YYYY
    - achievement bullet

This module parses that shape back so the UI can show exactly which facts
are missing (dates, employer, education, contact) and so the user can supply
them. Every edit here is deterministic and uses only values the user typed —
no model call and nothing inferred — so the truthfulness rule of the Resume
Agent holds for fixes too.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

# ── Vocabulary ──────────────────────────────────────────────────────────────

EXPERIENCE_SECTIONS = {
    "experience", "work experience", "professional experience", "employment",
    "employment history", "work history", "internships", "internship experience",
    "relevant experience",
}
EDUCATION_SECTIONS = {"education", "education and training", "academic background"}

_HEADING = re.compile(r"^(#{1,6})\s+")
_BULLET = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_DATE_WORD = re.compile(r"\b(?:present|current|now|ongoing)\b", re.I)
_RANGE_SPLIT = re.compile(r"\s*(?:\s-\s|–|—|\bto\b|-(?=\s*(?:\d|present|current|now)))\s*", re.I)
_PLACEHOLDER = re.compile(r"^\W*(?:not[_ ]provided|n/?a|tbd|unknown)\W*$", re.I)
_PLACEHOLDER_INLINE = re.compile(r"\[?\(?\bNOT[_ ]PROVIDED\b\)?\]?", re.I)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w/])\+?\d[\d\s().-]{7,}\d(?![\w/])")
_LINKEDIN = re.compile(r"(?:https?://)?(?:[\w-]+\.)?linkedin\.com/\S+", re.I)
_GITHUB = re.compile(r"(?:https?://)?(?:www\.)?github\.com/\S+", re.I)
_URL = re.compile(r"(?:https?://)?(?:www\.)?[\w-]+(?:\.[\w-]+)+/?\S*", re.I)
_CONTACT_HINT = re.compile(
    r"@|(?:\+?\d[\d\s().-]{7,})|(?:linkedin|github)\.com|https?://", re.I,
)
_CONTACT_SPLIT = re.compile(r"\s*(?:\||·|•|\u2022|;)\s*")

CONTACT_FIELDS = ("email", "phone", "location", "linkedin", "github", "portfolio")


def _plain(value: str) -> str:
    return re.sub(r"[*_`]", "", value).strip()


def is_placeholder(value: str | None) -> bool:
    return bool(value) and bool(_PLACEHOLDER.match(value.strip()))


def looks_like_dates(value: str) -> bool:
    return bool(_YEAR.search(value) or _DATE_WORD.search(value))


def clean_placeholders(markdown: str) -> str:
    """Drop NOT_PROVIDED-style placeholders so they never reach a PDF.

    Removes placeholder-only lines and heading parts, then removes section
    headings left with no content.
    """
    out: list[str] = []
    for raw in markdown.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        heading = _HEADING.match(stripped)
        if heading and "|" in stripped:
            marker = heading.group(1)
            parts = [p.strip() for p in stripped[heading.end():].split("|")]
            parts = [p for p in parts if p and not is_placeholder(_plain(p))]
            if not parts:
                continue
            line = f"{marker} " + " | ".join(parts)
        elif "|" in stripped and not heading:
            parts = [p.strip() for p in stripped.split("|")]
            kept = [p for p in parts if p and not is_placeholder(_plain(p))]
            if not kept:
                continue
            if len(kept) != len(parts):
                line = " | ".join(kept)
        body = _BULLET.sub("", _HEADING.sub("", line.strip()))
        if body and is_placeholder(_plain(body)):
            continue
        # Inline "(NOT_PROVIDED)" fragments inside prose.
        line = _PLACEHOLDER_INLINE.sub("", line).rstrip()
        line = re.sub(r"\s{2,}", " ", line) if line.strip() else ""
        if not line.strip() and raw.strip():
            continue
        out.append(line)

    # Remove `##` headings with nothing under them before the next `##`.
    result: list[str] = []
    for i, line in enumerate(out):
        m = _HEADING.match(line.strip())
        if m and len(m.group(1)) == 2:
            nxt = next(
                (ln for ln in out[i + 1:] if ln.strip()),
                None,
            )
            nm = _HEADING.match(nxt.strip()) if nxt else None
            if nxt is None or (nm and len(nm.group(1)) <= 2):
                continue
        result.append(line)
    return "\n".join(result).strip() + ("\n" if result else "")


# ── Heading parts ───────────────────────────────────────────────────────────

@dataclass
class EntryParts:
    role: str = ""
    employer: str = ""
    location: str = ""
    start: str = ""
    end: str = ""

    @property
    def dates(self) -> str:
        if self.start and self.end:
            return f"{self.start} - {self.end}"
        return self.start or self.end


def split_dates(value: str) -> tuple[str, str]:
    parts = [p.strip() for p in _RANGE_SPLIT.split(value, maxsplit=1) if p and p.strip()]
    if len(parts) == 2:
        return parts[0], parts[1]
    return value.strip(), ""


def split_heading(text: str) -> EntryParts:
    """`Role | Employer | Location | Dates` → parts (any part may be absent)."""
    parts = [p.strip() for p in _plain(text).split("|")]
    parts = [p for p in parts if p and not is_placeholder(p)]
    dates = ""
    if parts and looks_like_dates(parts[-1]):
        dates = parts.pop()
    start, end = split_dates(dates) if dates else ("", "")
    entry = EntryParts(start=start, end=end)
    if parts:
        entry.role = parts[0]
    if len(parts) > 1:
        entry.employer = parts[1]
    if len(parts) > 2:
        entry.location = ", ".join(parts[2:])
    return entry


def format_heading(entry: EntryParts) -> str:
    parts = [entry.role, entry.employer, entry.location, entry.dates]
    return "### " + " | ".join(p for p in parts if p)


def _unbalanced(value: str) -> bool:
    return value.count("(") != value.count(")") or value.count("[") != value.count("]")


# ── Parsing ─────────────────────────────────────────────────────────────────

@dataclass
class _Section:
    title: str
    line: int          # index of the `##` line
    end: int           # index one past the last line of the section


@dataclass
class _Entry:
    section: str
    kind: str          # "experience" | "education"
    index: int         # position within its kind
    line: int
    heading: str
    parts: EntryParts


@dataclass
class _Parsed:
    lines: list[str]
    name_line: int | None
    contact_lines: list[int]
    sections: list[_Section]
    entries: list[_Entry] = field(default_factory=list)


def _section_kind(title: str) -> str | None:
    key = _plain(title).rstrip(":").casefold()
    if key in EXPERIENCE_SECTIONS:
        return "experience"
    if key in EDUCATION_SECTIONS:
        return "education"
    return None


def _parse(markdown: str) -> _Parsed:
    lines = markdown.splitlines()
    name_line = None
    contact_lines: list[int] = []
    sections: list[_Section] = []
    first_section = None
    for i, raw in enumerate(lines):
        s = raw.strip()
        m = _HEADING.match(s)
        if m and len(m.group(1)) == 1 and name_line is None and first_section is None:
            name_line = i
            continue
        if m and len(m.group(1)) == 2:
            if sections:
                sections[-1].end = i
            sections.append(_Section(title=s[m.end():].strip(), line=i, end=len(lines)))
            if first_section is None:
                first_section = i
            continue
        if first_section is None and s and _CONTACT_HINT.search(_plain(s)):
            contact_lines.append(i)

    parsed = _Parsed(lines, name_line, contact_lines, sections)
    counters = {"experience": 0, "education": 0}
    for sec in sections:
        kind = _section_kind(sec.title)
        if not kind:
            continue
        for i in range(sec.line + 1, sec.end):
            s = lines[i].strip()
            m = _HEADING.match(s)
            if m and len(m.group(1)) >= 3:
                heading = s[m.end():].strip()
                parsed.entries.append(_Entry(
                    section=sec.title, kind=kind, index=counters[kind], line=i,
                    heading=heading, parts=split_heading(heading),
                ))
                counters[kind] += 1
    return parsed


def parse_contact(markdown: str) -> dict[str, str]:
    """Contact fields found in the header lines (before the first section)."""
    parsed = _parse(markdown)
    contact = dict.fromkeys(CONTACT_FIELDS, "")
    extras: list[str] = []
    for i in parsed.contact_lines:
        for part in _CONTACT_SPLIT.split(_plain(parsed.lines[i])):
            part = part.strip()
            if not part or is_placeholder(part):
                continue
            if not contact["email"] and _EMAIL.fullmatch(part):
                contact["email"] = part
            elif not contact["phone"] and _PHONE.fullmatch(part):
                contact["phone"] = part
            elif not contact["linkedin"] and _LINKEDIN.fullmatch(part):
                contact["linkedin"] = part
            elif not contact["github"] and _GITHUB.fullmatch(part):
                contact["github"] = part
            elif not contact["portfolio"] and _URL.fullmatch(part) and "." in part:
                contact["portfolio"] = part
            elif (not contact["location"] and len(part) < 60
                  and not any(ch.isdigit() for ch in part)):
                contact["location"] = part
            else:
                extras.append(part)
    return contact


# ── Review (what is missing) ────────────────────────────────────────────────

def _issue(code: str, message: str, **extra) -> dict:
    return {"code": code, "message": message, **extra}


def review_resume(markdown: str) -> dict:
    """Structured audit of a tailored resume.

    Returns the parsed contact block, experience and education entries (so the
    UI can pre-fill an edit form), and a list of concrete, user-fixable issues.
    """
    parsed = _parse(markdown)
    contact = parse_contact(markdown)
    experience: list[dict] = []
    education: list[dict] = []
    issues: list[dict] = []

    if not contact["email"]:
        issues.append(_issue("missing_email", "Add an email address to the contact line."))
    if not contact["phone"]:
        issues.append(_issue("missing_phone", "Add a phone number to the contact line."))

    for entry in parsed.entries:
        p = entry.parts
        item = {"index": entry.index, "heading": entry.heading, "section": entry.section,
                **asdict(p), "issues": []}
        if entry.kind == "experience":
            label = p.role or entry.heading
            if not p.employer:
                item["issues"].append("missing_employer")
                issues.append(_issue("missing_employer", f"Add the employer for “{label}”.",
                                     index=entry.index))
            elif _unbalanced(p.employer) or _unbalanced(p.role):
                item["issues"].append("truncated_employer")
                issues.append(_issue(
                    "truncated_employer",
                    f"The employer name “{p.employer}” looks cut off — enter the full name.",
                    index=entry.index,
                ))
            if not p.start:
                item["issues"].append("missing_dates")
                issues.append(_issue("missing_dates", f"Add start and end dates for “{label}”.",
                                     index=entry.index))
            experience.append(item)
        else:
            if not p.start:
                item["issues"].append("missing_dates")
            education.append(item)

    has_education_section = any(_section_kind(s.title) == "education" for s in parsed.sections)
    if not education:
        issues.append(_issue(
            "missing_education",
            "No education section. Add your degree, institution and graduation date.",
        ))

    return {
        "contact": contact,
        "experience": experience,
        "education": education,
        "has_education_section": has_education_section,
        "issues": issues,
    }


# ── Warning topics (hide LLM warnings the user has since resolved) ──────────

_WARNING_TOPICS = {
    "contact": re.compile(r"\b(?:contact details|contact info\w*|e-?mail|phone)\b", re.I),
    "dates": re.compile(r"\b(?:employment dates|start/end date|dates?|duration)\b", re.I),
    "education": re.compile(r"\beducation\b", re.I),
    "employer": re.compile(r"truncated mid|employer (?:name|line)|legal employer", re.I),
}
_ISSUE_TOPIC = {
    "missing_email": "contact", "missing_phone": "contact",
    "missing_dates": "dates", "missing_education": "education",
    "missing_employer": "employer", "truncated_employer": "employer",
}


def warning_topics(text: str) -> set[str]:
    return {topic for topic, rx in _WARNING_TOPICS.items() if rx.search(text)}


def filter_resolved_warnings(warnings: list[str], review: dict) -> list[str]:
    """Drop agent warnings about gaps that the resume no longer has.

    A warning is only dropped when every fixable topic it mentions is now
    resolved; warnings about genuine skill gaps (Azure, seniority, …) never
    match a topic and are always kept.
    """
    open_topics = {
        _ISSUE_TOPIC[i["code"]] for i in review.get("issues", []) if i["code"] in _ISSUE_TOPIC
    }
    kept = []
    for warning in warnings:
        topics = warning_topics(warning)
        if topics and not (topics & open_topics):
            continue
        kept.append(warning)
    return kept


# ── Fixes ───────────────────────────────────────────────────────────────────

def clean_field(value: str | None, limit: int = 160) -> str:
    """Normalize one user-typed value so it cannot break the Markdown shape."""
    if not value:
        return ""
    value = re.sub(r"\s+", " ", str(value)).replace("|", "/").strip()
    value = value.lstrip("#*->• ").strip()
    return value[:limit]


def _format_contact(contact: dict[str, str]) -> str:
    return " | ".join(contact[k] for k in CONTACT_FIELDS if contact.get(k))


def _education_section_insert_at(parsed: _Parsed) -> int:
    """Where a new EDUCATION section goes: after experience, else before skills, else end."""
    exp = [s for s in parsed.sections if _section_kind(s.title) == "experience"]
    if exp:
        return exp[-1].end
    for s in parsed.sections:
        if "skill" in s.title.casefold():
            return s.line
    return len(parsed.lines)


def apply_fixes(
    markdown: str,
    *,
    full_name: str = "",
    contact: dict[str, str | None] | None = None,
    experience: list[dict] | None = None,
    education: list[dict] | None = None,
) -> str:
    """Apply user-supplied facts to the resume Markdown.

    - contact: fields in CONTACT_FIELDS. ``None`` keeps the current value, an
      empty string removes it.
    - experience: ``{"index", role?, employer?, location?, start?, end?}`` —
      patches the Nth experience heading.
    - education: entries with ``index`` patch an existing education heading;
      entries without one are appended (``details`` becomes a bullet).

    Raises ValueError for an experience/education index that does not exist.
    """
    lines = markdown.splitlines()
    parsed = _parse(markdown)

    # Headings first (line numbers stay valid: they are replaced 1:1).
    by_kind = {(e.kind, e.index): e for e in parsed.entries}
    for kind, fixes in (("experience", experience or []), ("education", [
        f for f in (education or []) if f.get("index") is not None
    ])):
        for fix in fixes:
            entry = by_kind.get((kind, int(fix["index"])))
            if entry is None:
                raise ValueError(f"No {kind} entry at index {fix['index']}")
            p = entry.parts
            updated = EntryParts(
                role=_pick(fix, "role", p.role, fallback_key="degree"),
                employer=_pick(fix, "employer", p.employer, fallback_key="institution"),
                location=_pick(fix, "location", p.location),
                start=_pick(fix, "start", p.start),
                end=_pick(fix, "end", p.end),
            )
            if not updated.role and not updated.employer:
                raise ValueError(f"{kind} entry {fix['index']} needs a title or organization")
            lines[entry.line] = format_heading(updated)
            if kind == "education" and clean_field(fix.get("details"), 300):
                lines.insert(entry.line + 1, "- " + clean_field(fix.get("details"), 300))
                parsed = _parse("\n".join(lines))
                by_kind = {(e.kind, e.index): e for e in parsed.entries}

    # New education entries.
    new_edu = [f for f in (education or []) if f.get("index") is None]
    if new_edu:
        block: list[str] = []
        for fix in new_edu:
            entry = EntryParts(
                role=clean_field(fix.get("degree") or fix.get("role")),
                employer=clean_field(fix.get("institution") or fix.get("employer")),
                location=clean_field(fix.get("location")),
                start=clean_field(fix.get("start"), 40),
                end=clean_field(fix.get("end"), 40),
            )
            if not entry.role and not entry.employer:
                continue
            block.append(format_heading(entry))
            details = clean_field(fix.get("details"), 300)
            if details:
                block.append(f"- {details}")
        if block:
            parsed = _parse("\n".join(lines))
            edu = next((s for s in parsed.sections if _section_kind(s.title) == "education"), None)
            if edu is not None:
                at = edu.end
                while at > edu.line + 1 and not lines[at - 1].strip():
                    at -= 1
                lines[at:at] = block
            else:
                at = _education_section_insert_at(parsed)
                while at > 0 and at <= len(lines) and not lines[at - 1].strip():
                    at -= 1
                lines[at:at] = ["", "## EDUCATION", *block, ""]

    # Contact line + name.
    if contact is not None:
        parsed = _parse("\n".join(lines))
        current = parse_contact("\n".join(lines))
        for key in CONTACT_FIELDS:
            if key in contact and contact[key] is not None:
                current[key] = clean_field(contact[key], 200)
        new_line = _format_contact(current)
        insert_at = parsed.contact_lines[0] if parsed.contact_lines else (
            parsed.name_line + 1 if parsed.name_line is not None else 0
        )
        for i in reversed(parsed.contact_lines):
            del lines[i]
        if new_line:
            lines.insert(insert_at, new_line)

    parsed = _parse("\n".join(lines))
    if parsed.name_line is None and clean_field(full_name):
        lines.insert(0, f"# {clean_field(full_name)}")

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _pick(fix: dict, key: str, current: str, fallback_key: str | None = None) -> str:
    value = fix.get(key)
    if value is None and fallback_key:
        value = fix.get(fallback_key)
    if value is None:
        return current
    return clean_field(value, 40 if key in ("start", "end") else 160)


def ensure_contact(markdown: str, contact: dict[str, str | None]) -> str:
    """Fill contact fields that the resume lacks from user-entered profile data.

    Never overwrites a value already on the resume.
    """
    current = parse_contact(markdown)
    missing = {k: v for k, v in contact.items() if k in CONTACT_FIELDS and v and not current.get(k)}
    if not missing:
        return markdown
    return apply_fixes(markdown, contact=missing)


def apply_saved_facts(markdown: str, facts: dict) -> str:
    """Re-apply facts the user saved from an earlier fix to a fresh draft.

    Experience facts are matched to entries by role/employer text; only empty
    parts are filled so the new draft's wording wins. Education facts are
    added only when the draft has no education entries at all.
    """
    if not facts:
        return markdown
    review = review_resume(markdown)
    exp_fixes: list[dict] = []
    for saved in facts.get("experience") or []:
        key_role = (saved.get("role") or "").casefold()
        key_emp = (saved.get("employer_match") or saved.get("employer") or "").casefold()
        for entry in review["experience"]:
            role, emp = entry["role"].casefold(), entry["employer"].casefold()
            role_hit = key_role and (key_role in role or role in key_role) and role
            emp_hit = key_emp and emp and (emp[:12] in key_emp or key_emp[:12] in emp)
            if not (role_hit or emp_hit):
                continue
            fix: dict = {"index": entry["index"]}
            for k in ("employer", "location", "start", "end"):
                truncated = k == "employer" and "truncated_employer" in entry["issues"]
                if saved.get(k) and (not entry[k] or truncated):
                    fix[k] = saved[k]
            if len(fix) > 1:
                exp_fixes.append(fix)
            break
    edu = facts.get("education") or []
    new_edu = (
        [{k: v for k, v in e.items() if k != "index"} for e in edu]
        if not review["education"] else []
    )
    if not exp_fixes and not new_edu:
        return markdown
    return apply_fixes(markdown, experience=exp_fixes, education=new_edu)
