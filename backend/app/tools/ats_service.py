"""
ats_service.py — ATS (Applicant Tracking System) resume scoring.

Analyzes a resume against a job description for keyword coverage,
section completeness, and format compatibility with ATS parsers.
"""
from __future__ import annotations

import re
from collections import Counter


class ATSService:
    """Score a resume against a job description for ATS compatibility."""

    _STOPWORDS: set[str] = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "from", "by", "up", "as", "is", "it", "be", "we",
        "our", "your", "this", "that", "are", "was", "were", "been",
        "will", "can", "may", "has", "have", "had", "not", "no",
    }

    _SECTION_HEADERS: list[str] = [
        "experience", "education", "skills", "summary",
    ]

    _FORMAT_CHECKS: dict[str, callable] = {}

    def __init__(self) -> None:
        self._FORMAT_CHECKS = {
            "has_bullet_points": lambda t: bool(re.search(r"^[\s]*[•\-–—\*]\s", t, re.MULTILINE)),
            "consistent_dates": lambda t: len(re.findall(r"\d{4}\s*[-–—]\s*\d{4}|\d{4}\s*[-–—]\s*present", t.lower())) >= 1,
            "no_tables_detected": lambda t: "\t" not in t,
        }

    def _extract_keywords(self, text: str) -> set[str]:
        words = re.sub(r"[^a-zA-Z\s]", " ", text.lower()).split()
        return {w for w in words if len(w) >= 4 and w not in self._STOPWORDS}

    def score(self, resume_text: str, job_description: str) -> dict:
        jd_keywords = self._extract_keywords(job_description)
        resume_keywords = self._extract_keywords(resume_text)

        if not jd_keywords:
            return {
                "score": 0,
                "keyword_coverage": "0%",
                "missing_keywords": [],
                "suggestions": ["Job description had no extractable keywords"],
            }

        overlap = resume_keywords & jd_keywords
        keyword_coverage = len(overlap) / len(jd_keywords) * 100

        section_score = sum(
            25 for section in self._SECTION_HEADERS
            if section in resume_text.lower()
        )

        format_score = sum(
            33 for _, check in self._FORMAT_CHECKS.items()
            if check(resume_text)
        )
        if format_score > 100:
            format_score = 100

        total = int(keyword_coverage * 0.5 + section_score * 0.3 + format_score * 0.2)
        total = min(100, max(0, total))

        jd_word_counts = Counter(jd_keywords)
        missing = [
            kw for kw in jd_keywords - resume_keywords
            if jd_word_counts[kw] >= 2
        ]
        missing_sorted = sorted(
            missing, key=lambda w: jd_word_counts[w], reverse=True
        )[:10]

        suggestions: list[str] = []
        for kw in missing_sorted:
            suggestions.append(f"Add '{kw}' to your resume")
        if "experience" not in resume_text.lower():
            suggestions.append("Add an Experience section with dates and bullet points")
        if "skills" not in resume_text.lower():
            suggestions.append("Add a Skills section with relevant technologies")
        if "education" not in resume_text.lower():
            suggestions.append("Include an Education section with degrees and dates")

        return {
            "score": total,
            "keyword_coverage": f"{int(keyword_coverage)}%",
            "missing_keywords": missing_sorted,
            "suggestions": suggestions[:10],
            "section_score": section_score,
            "format_score": format_score,
        }
