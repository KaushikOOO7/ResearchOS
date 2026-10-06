"""
OpenAlex provider.

OpenAlex is the primary *metadata* source for ResearchOS: it covers journals,
conferences and preprints, exposes citation counts and open-access locations,
and requires no API key (a contact email gets you the polite pool).

Docs: https://docs.openalex.org/api-entities/works
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.paper import Paper, QueryAnalysis
from app.research.base import ResearchSource, build_paper
from app.utils.http import ProviderError, get_json
from app.utils.logging_setup import get_logger

logger = get_logger("openalex")

OPENALEX_API_URL = "https://api.openalex.org/works"

_SELECT_FIELDS = ",".join(
    [
        "id",
        "doi",
        "title",
        "display_name",
        "publication_year",
        "publication_date",
        "authorships",
        "abstract_inverted_index",
        "cited_by_count",
        "primary_location",
        "best_oa_location",
        "open_access",
        "type",
        "keywords",
    ]
)


def reconstruct_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> str:
    """
    Rebuild plain abstract text from OpenAlex's inverted index.

    OpenAlex stores abstracts as ``{word: [positions]}`` (a legacy of
    copyright constraints). Rebuilding is deterministic and lossless.
    """
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""
    positioned: List[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        if not isinstance(positions, (list, tuple)):
            continue
        for position in positions:
            if isinstance(position, int):
                positioned.append((position, word))
    if not positioned:
        return ""
    positioned.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positioned)


def _pdf_url_from_location(location: Optional[dict]) -> Optional[str]:
    if not isinstance(location, dict):
        return None
    for key in ("pdf_url", "landing_page_url"):
        value = location.get(key)
        if isinstance(value, str) and value.startswith("http") and key == "pdf_url":
            return value
    return None


class OpenAlexSource(ResearchSource):
    """OpenAlex works index (journals, conferences, preprints)."""

    name = "OpenAlex"
    tier = 1
    source_score = 92.0

    def fetch(self, query: str, limit: int, query_analysis: QueryAnalysis) -> List[Paper]:
        params: Dict[str, Any] = {
            "search": query,
            "per-page": max(1, min(limit, 100)),
            "page": 1,
            "select": _SELECT_FIELDS,
            "filter": "is_paratext:false",
        }
        if settings.openalex_email:
            params["mailto"] = settings.openalex_email

        payload = get_json(self.name, OPENALEX_API_URL, params=params)

        results = (payload or {}).get("results")
        if results is None:
            raise ProviderError(self.name, "unexpected response shape")

        papers: List[Paper] = []
        for work in results:
            paper = self._parse_work(work)
            if paper and paper.title:
                papers.append(paper)
        return papers

    def _parse_work(self, work: Dict[str, Any]) -> Optional[Paper]:
        if not isinstance(work, dict):
            return None

        title = work.get("title") or work.get("display_name") or ""
        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

        authors: List[str] = []
        for authorship in work.get("authorships") or []:
            author = (authorship or {}).get("author") or {}
            name = author.get("display_name")
            if name:
                authors.append(name)

        primary_location = work.get("primary_location") or {}
        source_info = (primary_location or {}).get("source") or {}
        venue = source_info.get("display_name")

        best_oa = work.get("best_oa_location") or {}
        oa_info = work.get("open_access") or {}
        pdf_url = _pdf_url_from_location(best_oa)
        if not pdf_url:
            oa_url = oa_info.get("oa_url")
            if isinstance(oa_url, str) and oa_url.lower().endswith(".pdf"):
                pdf_url = oa_url

        keywords = [
            keyword.get("display_name")
            for keyword in (work.get("keywords") or [])
            if isinstance(keyword, dict) and keyword.get("display_name")
        ]

        citations = work.get("cited_by_count")
        if not isinstance(citations, int):
            citations = None

        return build_paper(
            title=title,
            abstract=abstract,
            authors=authors,
            year=work.get("publication_year"),
            doi=work.get("doi"),
            venue=venue,
            paper_url=work.get("id") or primary_location.get("landing_page_url"),
            pdf_url=pdf_url,
            citation_count=citations,
            is_open_access=bool(oa_info.get("is_oa")) if oa_info else None,
            keywords=keywords,
            subjects=[source_info.get("type")] if source_info.get("type") else [],
            doc_type=work.get("type"),
            source_score=self.source_score,
            source=self.name,
        )
