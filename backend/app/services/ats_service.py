"""
ATS Resume Scoring Engine.

Implements keyword coverage (50%), readability (30%), and format compliance (20%)
weighted sub-scores to produce a composite ATS compatibility score (0-100).

Based on parsing rules for Greenhouse, Workday, Taleo, iCIMS (2026).

No external NLP dependencies — uses stdlib re, collections, math only.
"""
import collections
import math
import re
from dataclasses import dataclass, field


@dataclass
class AtsScoreResult:
    """Result of an ATS scoring analysis."""

    composite_score: int
    keyword_score: int
    readability_score: int
    format_score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    suggestions: list[str]
    flesch_kincaid: float
    avg_sentence_length: float
    format_checks: dict[str, bool]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SECTION_PATTERNS = {
    "experience": r"(work\s+)?experience|employment|work\s+history",
    "education": r"education|academic|degree",
    "skills": r"(technical\s+)?skills?|technologies|competencies|expertise",
    "certifications": r"certif(ications?|ied)|licenses?",
    "summary": r"summary|profile|objective|about\s+me",
    "projects": r"projects?|portfolio|open.?source",
}

STANDARD_HEADINGS = {
    "experience",
    "education",
    "skills",
    "summary",
    "certifications",
    "projects",
}

STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "have", "from", "are", "will", "you",
    "our", "they", "were", "been", "has", "had", "his", "her", "its", "their", "there",
    "what", "when", "which", "who", "can", "may", "should", "would", "could", "also",
    "into", "than", "then", "some", "just", "about", "over", "each", "but", "not",
    "all", "more", "out", "one", "two", "new", "get", "use", "per", "via",
}

# JD section markers for keyword importance ordering
_TITLE_MARKERS = re.compile(
    r"(job\s+title|position|role)\s*[:—\-]", re.IGNORECASE
)
_REQUIRED_MARKERS = re.compile(
    r"(required|must\s+have|requirements|qualifications|minimum)", re.IGNORECASE
)
_PREFERRED_MARKERS = re.compile(
    r"(preferred|nice\s+to\s+have|bonus|desired|plus)", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Pure function: weighted composite
# ---------------------------------------------------------------------------


def compute_weighted_composite(keyword: int, readability: int, format_: int) -> int:
    """Compute weighted ATS composite score.

    Formula: round(keyword * 0.5 + readability * 0.3 + format_ * 0.2)
    Result clamped to [0, 100].
    """
    raw = round(keyword * 0.5 + readability * 0.3 + format_ * 0.2)
    return max(0, min(100, raw))


# ---------------------------------------------------------------------------
# Flesch-Kincaid readability
# ---------------------------------------------------------------------------


def _count_syllables(word: str) -> int:
    """Estimate syllable count for an English word."""
    word = word.lower().strip()
    if not word:
        return 0
    # Remove trailing silent e
    if word.endswith("e") and len(word) > 2:
        word = word[:-1]
    # Count vowel groups
    vowels = "aeiou"
    count = 0
    prev_vowel = False
    for ch in word:
        if ch in vowels:
            if not prev_vowel:
                count += 1
            prev_vowel = True
        else:
            prev_vowel = False
    return max(count, 1)


def compute_flesch_kincaid(text: str) -> tuple[float, float]:
    """Compute Flesch-Kincaid reading grade level and average sentence length.

    Returns (grade_level, avg_sentence_length).
    """
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0.0, 0.0

    words = re.findall(r"[a-zA-Z]+", text)
    if not words:
        return 0.0, 0.0

    total_words = len(words)
    total_sentences = len(sentences)
    total_syllables = sum(_count_syllables(w) for w in words)

    avg_sentence_length = total_words / total_sentences
    avg_syllables_per_word = total_syllables / total_words

    # Flesch-Kincaid Grade Level formula
    grade_level = (
        0.39 * avg_sentence_length + 11.8 * avg_syllables_per_word - 15.59
    )

    return round(grade_level, 2), round(avg_sentence_length, 2)


def _readability_score_from_fk(grade_level: float) -> int:
    """Convert Flesch-Kincaid grade level to a 0-100 readability score.

    Ideal resume readability: grade 8-12. Penalizes too complex or too simple.
    """
    if 8.0 <= grade_level <= 12.0:
        return 100
    elif 6.0 <= grade_level < 8.0 or 12.0 < grade_level <= 14.0:
        return 80
    elif 4.0 <= grade_level < 6.0 or 14.0 < grade_level <= 16.0:
        return 60
    elif grade_level < 4.0:
        return 40
    else:  # > 16
        return 40


# ---------------------------------------------------------------------------
# Keyword extraction and matching
# ---------------------------------------------------------------------------


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text, filtering stop words."""
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z+#.]{2,}\b", text.lower())
    filtered = [t for t in tokens if t not in STOP_WORDS]
    counter = collections.Counter(filtered)
    return {word for word, _ in counter.most_common(50)}


def _extract_jd_sections(jd_text: str) -> dict[str, str]:
    """Split JD text into rough sections for importance ordering."""
    lines = jd_text.split("\n")
    sections: dict[str, list[str]] = {"title": [], "required": [], "preferred": [], "other": []}
    current = "other"

    for line in lines:
        if _TITLE_MARKERS.search(line):
            current = "title"
        elif _REQUIRED_MARKERS.search(line):
            current = "required"
        elif _PREFERRED_MARKERS.search(line):
            current = "preferred"
        sections[current].append(line)

    return {k: "\n".join(v) for k, v in sections.items()}


def get_missing_keywords(resume_text: str, jd_text: str) -> list[str]:
    """Return keywords in JD not in resume, ordered by importance.

    Order: title matches first, then required skills, then preferred skills.
    """
    if not jd_text or not jd_text.strip():
        return []

    resume_kw = _extract_keywords(resume_text)
    jd_sections = _extract_jd_sections(jd_text)

    # Extract keywords per section
    title_kw = _extract_keywords(jd_sections.get("title", ""))
    required_kw = _extract_keywords(jd_sections.get("required", ""))
    preferred_kw = _extract_keywords(jd_sections.get("preferred", ""))
    other_kw = _extract_keywords(jd_sections.get("other", ""))

    # All JD keywords
    all_jd_kw = title_kw | required_kw | preferred_kw | other_kw

    # Missing = in JD but not in resume
    missing = all_jd_kw - resume_kw

    # Order by importance: title > required > preferred > other
    ordered: list[str] = []
    seen: set[str] = set()

    for kw_set in [title_kw, required_kw, preferred_kw, other_kw]:
        for kw in sorted(kw_set & missing):
            if kw not in seen:
                ordered.append(kw)
                seen.add(kw)

    return ordered


# ---------------------------------------------------------------------------
# Format compliance checks
# ---------------------------------------------------------------------------


def _check_format_compliance(text: str) -> dict[str, bool]:
    """Check format compliance: contact info, no tables, standard headings."""
    has_contact = bool(
        re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        or re.search(
            r"[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}", text
        )
    )

    has_tables = bool(
        re.search(r"\||\+---", text)
        or re.search(r"<table", text, re.IGNORECASE)
    )

    has_standard_headings = False
    for name, pattern in SECTION_PATTERNS.items():
        if name in STANDARD_HEADINGS and re.search(pattern, text, re.IGNORECASE):
            has_standard_headings = True
            break

    return {
        "has_contact_info": has_contact,
        "no_tables": not has_tables,
        "has_standard_headings": has_standard_headings,
    }


def _format_score_from_checks(checks: dict[str, bool]) -> int:
    """Compute format score (0-100) from compliance checks."""
    total_checks = len(checks)
    passed = sum(1 for v in checks.values() if v)
    score = round(passed / total_checks * 100) if total_checks > 0 else 0
    return score


# ---------------------------------------------------------------------------
# Suggestion generation
# ---------------------------------------------------------------------------


def generate_suggestions(score_result: AtsScoreResult) -> list[str]:
    """Generate actionable suggestions based on ATS score result.

    Returns ≥3 suggestions when composite_score < 60.
    """
    suggestions: list[str] = []

    # Keyword-related suggestions
    if score_result.keyword_score < 70 and score_result.missing_keywords:
        top_missing = score_result.missing_keywords[:5]
        suggestions.append(
            f"Add missing keywords to your resume: {', '.join(top_missing)}"
        )

    if score_result.keyword_score < 50:
        suggestions.append(
            "Rewrite your skills section to mirror the exact terminology used in the job description"
        )

    # Readability suggestions
    if score_result.readability_score < 70:
        if score_result.avg_sentence_length > 25:
            suggestions.append(
                "Shorten sentences to improve readability — aim for 15-20 words per sentence"
            )
        elif score_result.avg_sentence_length < 8:
            suggestions.append(
                "Expand bullet points with more context — sentences are too brief for ATS parsing"
            )
        if score_result.flesch_kincaid > 14:
            suggestions.append(
                "Simplify language — use common industry terms instead of overly academic vocabulary"
            )

    # Format compliance suggestions
    if not score_result.format_checks.get("has_contact_info", True):
        suggestions.append(
            "Add contact information (email, phone) at the top of your resume"
        )

    if not score_result.format_checks.get("no_tables", True):
        suggestions.append(
            "Remove tables and use plain text formatting — most ATS systems cannot parse tables"
        )

    if not score_result.format_checks.get("has_standard_headings", True):
        suggestions.append(
            "Use standard section headings (Experience, Education, Skills) for ATS compatibility"
        )

    # General suggestions when score is low
    if score_result.composite_score < 60:
        if score_result.keyword_score < 60:
            suggestions.append(
                "Tailor your resume specifically to this job description — "
                "generic resumes score poorly with ATS systems"
            )
        if len(suggestions) < 3:
            suggestions.append(
                "Consider adding a skills summary section that lists key technologies "
                "and competencies matching the job requirements"
            )
        if len(suggestions) < 3:
            suggestions.append(
                "Quantify your achievements with metrics (percentages, dollar amounts, team sizes) "
                "to improve ATS keyword matching"
            )
        # Guarantee ≥3 suggestions when composite < 60
        if len(suggestions) < 3:
            suggestions.append(
                "Review the job posting requirements section and ensure each required skill "
                "appears at least once in your resume"
            )

    return suggestions


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------


def compute_ats_score(resume_text: str, jd_text: str) -> AtsScoreResult:
    """Compute full ATS score for a resume against a job description.

    Returns AtsScoreResult with composite score (0-100), sub-scores,
    missing keywords, and suggestions.
    """
    if not resume_text or not resume_text.strip():
        raise ValueError("resume_text cannot be empty")
    if not jd_text or not jd_text.strip():
        raise ValueError("jd_text cannot be empty")

    # Keyword score
    resume_kw = _extract_keywords(resume_text)
    jd_kw = _extract_keywords(jd_text)
    if jd_kw:
        matched = sorted(jd_kw & resume_kw)
        keyword_score = round(len(matched) / len(jd_kw) * 100)
        keyword_score = max(0, min(100, keyword_score))
    else:
        matched = []
        keyword_score = 50

    # Readability score (Flesch-Kincaid)
    flesch_kincaid, avg_sentence_length = compute_flesch_kincaid(resume_text)
    readability_score = _readability_score_from_fk(flesch_kincaid)

    # Format compliance
    format_checks = _check_format_compliance(resume_text)
    format_score = _format_score_from_checks(format_checks)

    # Missing keywords (ordered by importance)
    missing_keywords = get_missing_keywords(resume_text, jd_text)

    # Composite score
    composite_score = compute_weighted_composite(keyword_score, readability_score, format_score)

    # Build result
    result = AtsScoreResult(
        composite_score=composite_score,
        keyword_score=keyword_score,
        readability_score=readability_score,
        format_score=format_score,
        matched_keywords=matched,
        missing_keywords=missing_keywords,
        suggestions=[],
        flesch_kincaid=flesch_kincaid,
        avg_sentence_length=avg_sentence_length,
        format_checks=format_checks,
    )

    # Generate suggestions
    result.suggestions = generate_suggestions(result)

    return result
