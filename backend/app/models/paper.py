"""
Canonical ResearchOS paper model.

Every provider normalises its payload into this single schema (see the
project brief, section 39). Fields that a provider does not supply stay
``None``/empty -- ResearchOS never invents metadata.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.utils.text import normalize_arxiv_id, normalize_doi, normalize_title


def build_paper_id(
    doi: Optional[str] = None,
    arxiv_id: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """
    Deterministic, stable identifier for a paper.

    Preference order: DOI -> arXiv id -> normalised title. The identifier is
    stable across sources, which is what makes cross-source deduplication and
    ``GET /papers/{id}`` work.
    """
    doi_key = normalize_doi(doi)
    if doi_key:
        key = f"doi:{doi_key}"
    else:
        arxiv_key = normalize_arxiv_id(arxiv_id)
        if arxiv_key:
            key = f"arxiv:{arxiv_key}"
        else:
            key = f"title:{normalize_title(title or '')}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return f"p_{digest[:16]}"


class Paper(BaseModel):
    """Normalised paper record used throughout the backend."""

    id: str = ""
    title: str = ""
    authors: List[str] = Field(default_factory=list)
    abstract: str = ""
    year: Optional[int] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    venue: Optional[str] = None
    paper_url: Optional[str] = None
    pdf_url: Optional[str] = None
    source: str = ""
    sources: List[str] = Field(default_factory=list)
    citation_count: Optional[int] = None
    is_open_access: Optional[bool] = None
    keywords: List[str] = Field(default_factory=list)
    subjects: List[str] = Field(default_factory=list)
    type: Optional[str] = None

    # --- Ranking (0-100) ---------------------------------------------------
    relevance_score: float = 0.0
    quality_score: float = 0.0
    recency_score: Optional[float] = None
    citation_score: Optional[float] = None
    source_score: float = 0.0
    overall_score: float = 0.0

    # --- Explainability ----------------------------------------------------
    score_explanations: Dict[str, str] = Field(default_factory=dict)
    matched_terms: List[str] = Field(default_factory=list)
    rank: Optional[int] = None

    def model_post_init(self, __context) -> None:  # noqa: D105 - pydantic hook
        if not self.id:
            self.id = build_paper_id(self.doi, self.arxiv_id, self.title)
        if self.source and self.source not in self.sources:
            self.sources = [self.source, *self.sources]

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    @property
    def quality_label(self) -> str:
        """
        Coarse, explicitly heuristic label derived from ``quality_score``.

        It reflects *metadata completeness / venue signals*, not a judgement
        about the scientific merit of the work.
        """
        if self.quality_score >= 75:
            return "High"
        if self.quality_score >= 50:
            return "Medium"
        if self.quality_score > 0:
            return "Basic"
        return "Unknown"

    @property
    def authors_display(self) -> str:
        """Compact author string for cards (``A, B et al.``)."""
        if not self.authors:
            return "Authors not available"
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return f"{', '.join(self.authors[:3])} et al."

    def to_public_dict(self) -> dict:
        """Serialise with derived fields the frontend renders directly."""
        data = self.model_dump()
        data["quality_label"] = self.quality_label
        data["authors_display"] = self.authors_display
        return data


class SourceStatus(BaseModel):
    """Per-provider outcome, surfaced to the UI for transparency."""

    name: str
    ok: bool
    result_count: int = 0
    elapsed_ms: int = 0
    error: Optional[str] = None
    configured: bool = True


class QueryAnalysis(BaseModel):
    """Deterministic understanding of the user's research query."""

    original: str
    normalized: str
    terms: List[str] = Field(default_factory=list)
    phrases: List[str] = Field(default_factory=list)
    acronyms: Dict[str, str] = Field(default_factory=dict)
    is_biomedical: bool = False
    wants_recent: bool = False
    year_from: Optional[int] = None
    topical_terms: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class SearchStats(BaseModel):
    """Pipeline telemetry shown in the UI and printed in the logs."""

    candidates_collected: int = 0
    duplicates_removed: int = 0
    returned: int = 0
    providers_queried: int = 0
    providers_succeeded: int = 0
    elapsed_ms: int = 0
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
