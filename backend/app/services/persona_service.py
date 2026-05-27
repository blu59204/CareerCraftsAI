"""
persona_service.py — Resume Persona matching utilities.

Pure functions for keyword overlap computation and best-fit persona selection.
"""
import re


def compute_keyword_overlap(persona_keywords: list[str], jd_keywords: list[str]) -> float:
    """Compute overlap ratio between persona keywords and JD keywords.

    Returns float in [0.0, 1.0].
    """
    if not persona_keywords or not jd_keywords:
        return 0.0
    persona_set = {k.lower().strip() for k in persona_keywords}
    jd_set = {k.lower().strip() for k in jd_keywords}
    if not jd_set:
        return 0.0
    overlap = persona_set & jd_set
    return len(overlap) / len(jd_set)


def extract_jd_keywords(jd_text: str) -> list[str]:
    """Extract meaningful keywords from JD text."""
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z+#.]{2,}\b", jd_text.lower())
    stop = {"the", "and", "for", "with", "that", "this", "have", "from", "are", "will",
            "you", "our", "they", "were", "been", "has", "had", "can", "may", "should",
            "would", "could", "also", "into", "than", "then", "some", "just", "about"}
    from collections import Counter
    counter = Counter(t for t in tokens if t not in stop)
    return [w for w, _ in counter.most_common(30)]


def select_best_persona(personas: list[dict], jd_text: str) -> tuple[dict | None, float]:
    """Select the persona with highest keyword overlap to the JD.

    Returns (best_persona, overlap_score). Returns (None, 0.0) if no personas.
    """
    if not personas:
        return None, 0.0

    jd_keywords = extract_jd_keywords(jd_text)
    best = None
    best_score = 0.0

    for persona in personas:
        score = compute_keyword_overlap(persona.get("target_keywords", []), jd_keywords)
        if score > best_score:
            best_score = score
            best = persona

    return best, best_score
