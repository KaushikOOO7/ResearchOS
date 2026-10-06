"""
Query understanding.

The first stage of the ResearchOS pipeline. It converts the user's free-text
idea into a structured, *inspectable* representation:

    USER QUERY -> tokenise -> keyphrases -> acronym expansion -> intent
              -> domain detection (e.g. biomedical) -> QueryAnalysis

Deliberately deterministic (no LLM call) so it is fast, free, reproducible
and unit-testable. A model-assisted variant can be layered on top later
without changing the interface.
"""

from __future__ import annotations

from typing import List

from app.models.paper import QueryAnalysis
from app.utils.text import (
    detect_year_intent,
    extract_acronyms,
    is_biomedical,
    keyphrases,
    normalize_space,
    normalize_title,
    stem,
)


def analyze_query(query: str) -> QueryAnalysis:
    """
    Build a :class:`QueryAnalysis` for ``query``.

    ``topical_terms`` contains the stemmed topic tokens plus acronym
    expansions, which is exactly what the ranker matches against paper
    metadata.
    """
    original = normalize_space(query or "")
    phrases, terms = keyphrases(original)
    acronyms = extract_acronyms(original)
    biomedical = is_biomedical(original)
    wants_recent, year_from = detect_year_intent(original)

    topical_terms: List[str] = []
    for term in terms:
        stemmed = stem(term)
        if stemmed not in topical_terms:
            topical_terms.append(stemmed)
    # Add expansions as first-class topical terms (deduplicated).
    for short, expansion in acronyms.items():
        for token in expansion.split():
            stemmed = stem(token)
            if stemmed not in topical_terms:
                topical_terms.append(stemmed)

    notes: List[str] = []
    if acronyms:
        pairs = ", ".join(f"{short.upper()} → {expansion}" for short, expansion in list(acronyms.items())[:3])
        notes.append(f"Expanded acronyms: {pairs}")
    if biomedical:
        notes.append("Biomedical signal detected — PubMed included as a source")
    if wants_recent:
        notes.append("Recency intent detected — newer papers are ranked higher")
    if year_from:
        notes.append(f"Year filter applied: papers from {year_from} onwards")
    if not terms:
        notes.append("Query contained only generic words; results may be broad")

    return QueryAnalysis(
        original=original,
        normalized=normalize_title(original),
        terms=terms,
        phrases=phrases,
        acronyms=acronyms,
        is_biomedical=biomedical,
        wants_recent=wants_recent,
        year_from=year_from,
        topical_terms=topical_terms,
        notes=notes,
    )
