"""
Paper normalisation.

Every provider returns a different shape. This module is the single place that
converts raw provider fields into the canonical ResearchOS paper schema, so the
deduplicator, the ranker and the API all see identical structures.

Rules enforced here (and nowhere else):
  * markup / control characters are stripped, whitespace is collapsed,
  * DOIs / arXiv ids are canonicalised,
  * authors are de-duplicated and bounded,
  * ``year`` and ``published_date`` are validated (a provider that reports
    "2024-03-01" also gets ``year = 2024``),
  * **nothing is invented** — a field the provider did not supply stays
    ``None`` / empty, which the API surfaces as "Not available".
"""

from __future__ import annotations

import re
from typing import Any, List, Optional

from app.models.paper import Paper
from app.utils.logging_setup import get_logger
from app.utils.text import normalize_arxiv_id, normalize_doi, normalize_space, sanitize_external_text

logger = get_logger("normalizer")

#: Document types ResearchOS keeps verbatim from the provider.
_DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")

#: Hard caps keep payloads reasonable (see "performance" requirements).
MAX_AUTHORS = 40
MAX_KEYWORDS = 12
MAX_SUBJECTS = 8
MAX_ABSTRACT_CHARS = 6000


def normalize_year(value: Any) -> Optional[int]:
    """Return a sane publication year, or ``None`` when unavailable/invalid."""
    if isinstance(value, int) and 1800 < value < 2100:
        return value
    if isinstance(value, str):
        match = re.search(r"\b(18|19|20|21)\d{2}\b", value)
        if match:
            year = int(match.group(0))
            if 1800 < year < 2100:
                return year
    return None


def normalize_date(value: Any, fallback_year: Optional[int] = None) -> Optional[str]:
    """
    Normalise a publication date to ``YYYY-MM-DD`` / ``YYYY-MM`` / ``YYYY``.

    Providers are inconsistent (ISO timestamps, ``[2024, 3, 1]`` arrays of date
    parts, "2024 Mar"). Anything unrecognisable is dropped rather than guessed.
    """
    if value is None:
        return None

    # Crossref style date-parts: [[2024, 3, 1]]
    if isinstance(value, (list, tuple)) and value:
        first = value[0]
        if isinstance(first, (list, tuple)):
            value = first
        if isinstance(value, (list, tuple)) and value and isinstance(value[0], int):
            parts = [int(part) for part in value[:3] if isinstance(part, int)]
            return _format_parts(parts)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
        if iso:
            return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
        year_month = re.match(r"^(\d{4})-(\d{2})$", text)
        if year_month:
            return text
        if re.match(r"^(\d{4})$", text):
            return text
        # "2024 Mar 01", "Mar 2024", "2024 Mar"
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        year_match = re.search(r"\b(18|19|20|21)\d{2}\b", text)
        if year_match:
            year = int(year_match.group(0))
            month_token = re.search(r"[A-Za-z]{3}", text)
            if month_token:
                month = months.get(month_token.group(0).lower())
                if month:
                    day_match = re.search(r"\b(\d{1,2})\b(?!.*\b\d{4}\b)", text)
                    if day_match and 1 <= int(day_match.group(1)) <= 31:
                        return f"{year}-{month:02d}-{int(day_match.group(1)):02d}"
                    return f"{year}-{month:02d}"
            return str(year)

    if isinstance(value, int):
        return normalize_date(str(value))

    if fallback_year:
        return str(fallback_year)
    return None


def _format_parts(parts: List[int]) -> Optional[str]:
    if not parts:
        return None
    year = parts[0]
    if not (1800 < year < 2100):
        return None
    if len(parts) >= 3 and 1 <= parts[1] <= 12 and 1 <= parts[2] <= 31:
        return f"{year}-{parts[1]:02d}-{parts[2]:02d}"
    if len(parts) >= 2 and 1 <= parts[1] <= 12:
        return f"{year}-{parts[1]:02d}"
    return str(year)


def normalize_authors(authors: Optional[List[Any]]) -> List[str]:
    """Clean, de-duplicate and bound an author list."""
    cleaned: List[str] = []
    for author in authors or []:
        name = normalize_space(str(author or ""))
        if not name or name in cleaned:
            continue
        cleaned.append(name)
        if len(cleaned) >= MAX_AUTHORS:
            break
    return cleaned


def build_paper(
    title: str,
    source: str,
    abstract: str = "",
    authors: Optional[List[str]] = None,
    year: Optional[int] = None,
    published_date: Optional[Any] = None,
    doi: Optional[str] = None,
    arxiv_id: Optional[str] = None,
    venue: Optional[str] = None,
    journal: Optional[str] = None,
    paper_url: Optional[str] = None,
    pdf_url: Optional[str] = None,
    citation_count: Optional[int] = None,
    is_open_access: Optional[bool] = None,
    keywords: Optional[List[str]] = None,
    subjects: Optional[List[str]] = None,
    doc_type: Optional[str] = None,
    source_score: Optional[float] = None,
) -> Paper:
    """
    Build a canonical :class:`Paper` from raw provider fields.

    Providers call this and nothing else — all cross-provider hygiene lives
    here, which is what makes deduplication and ranking reliable.
    """
    clean_title = sanitize_external_text(title or "", max_chars=600)
    clean_abstract = sanitize_external_text(abstract or "", max_chars=MAX_ABSTRACT_CHARS)

    normalised_authors = normalize_authors(authors)

    clean_keywords: List[str] = []
    for keyword in keywords or []:
        value = sanitize_external_text(str(keyword or ""), max_chars=80).lower()
        if value and value not in clean_keywords:
            clean_keywords.append(value)
        if len(clean_keywords) >= MAX_KEYWORDS:
            break

    clean_subjects: List[str] = []
    for subject in subjects or []:
        value = sanitize_external_text(str(subject or ""), max_chars=80)
        if value and value not in clean_subjects:
            clean_subjects.append(value)
        if len(clean_subjects) >= MAX_SUBJECTS:
            break

    normalised_year = normalize_year(year)
    normalised_date = normalize_date(published_date, fallback_year=normalised_year)
    # A dated record always has a year, even when the provider only sent a date.
    if normalised_year is None and normalised_date:
        normalised_year = normalize_year(normalised_date[:4])

    citations = citation_count if isinstance(citation_count, int) and citation_count >= 0 else None

    return Paper(
        title=clean_title,
        abstract=clean_abstract,
        authors=normalised_authors,
        year=normalised_year,
        published_date=normalised_date,
        doi=normalize_doi(doi) or None,
        arxiv_id=normalize_arxiv_id(arxiv_id) or None,
        venue=sanitize_external_text(venue or "", max_chars=200) or None,
        journal=sanitize_external_text(journal or "", max_chars=200) or None,
        paper_url=paper_url or None,
        pdf_url=pdf_url or None,
        source=source,
        sources=[source],
        citation_count=citations,
        is_open_access=is_open_access,
        keywords=clean_keywords,
        subjects=clean_subjects,
        type=doc_type,
        source_score=source_score if source_score is not None else 70.0,
    )
