"""
Semantic Scholar provider (optional).

Only enabled when ``SEMANTIC_SCHOLAR_API_KEY`` is set. Without a key the
public pool frequently returns HTTP 429, and ResearchOS prefers to skip a
provider rather than hammer a shared endpoint or block the search.

The key is sent as a request header (never in the URL, never logged).

Docs: https://api.semanticscholar.org/api-docs/graph
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.paper import Paper, QueryAnalysis
from app.research.base import ResearchSource, build_paper
from app.utils.http import ProviderError, get_json
from app.utils.logging_setup import get_logger

logger = get_logger("semantic_scholar")

S2_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

_FIELDS = ",".join(
    [
        "title",
        "abstract",
        "year",
        "venue",
        "publicationVenue",
        "authors",
        "externalIds",
        "openAccessPdf",
        "citationCount",
        "publicationTypes",
        "fieldsOfStudy",
    ]
)

#: S2 publication types that indicate a real research paper.
_PAPER_TYPES = {"JournalArticle", "Conference", "Review", "Book", "BookSection", "Dataset"}


class SemanticScholarSource(ResearchSource):
    """Semantic Scholar Graph API (key required)."""

    name = "Semantic Scholar"
    tier = 2
    source_score = 85.0

    def is_configured(self) -> bool:
        return bool(settings.semantic_scholar_api_key)

    def fetch(self, query: str, limit: int, query_analysis: QueryAnalysis) -> List[Paper]:
        payload = get_json(
            self.name,
            S2_API_URL,
            params={
                "query": query,
                "limit": max(1, min(limit, 100)),
                "fields": _FIELDS,
            },
            headers={"x-api-key": settings.semantic_scholar_api_key},
        )

        data = (payload or {}).get("data")
        if data is None:
            raise ProviderError(self.name, "unexpected response shape")

        papers: List[Paper] = []
        for item in data:
            paper = self._parse_item(item)
            if paper and paper.title:
                papers.append(paper)
        return papers

    def _parse_item(self, item: Dict[str, Any]) -> Optional[Paper]:
        if not isinstance(item, dict):
            return None

        external_ids = item.get("externalIds") or {}

        pdf_url = None
        open_access = item.get("openAccessPdf") or {}
        if isinstance(open_access, dict) and open_access.get("url"):
            pdf_url = open_access["url"]

        citation_count = item.get("citationCount")
        if not isinstance(citation_count, int):
            citation_count = None

        authors = [
            author.get("name")
            for author in (item.get("authors") or [])
            if isinstance(author, dict) and author.get("name")
        ]

        fields_of_study = item.get("fieldsOfStudy") or []

        venue = item.get("venue") or ""
        publication_venue = item.get("publicationVenue") or {}
        if not venue and isinstance(publication_venue, dict):
            venue = publication_venue.get("name") or ""

        doc_type = None
        types = item.get("publicationTypes") or []
        if types:
            doc_type = "article" if "JournalArticle" in types else types[0]

        return build_paper(
            title=item.get("title") or "",
            abstract=item.get("abstract") or "",
            authors=authors,
            year=item.get("year"),
            doi=external_ids.get("DOI"),
            arxiv_id=external_ids.get("ArXiv"),
            venue=venue or None,
            paper_url=(
                f"https://www.semanticscholar.org/paper/{item['paperId']}"
                if item.get("paperId")
                else None
            ),
            pdf_url=pdf_url,
            citation_count=citation_count,
            is_open_access=bool(pdf_url) if pdf_url is not None else None,
            keywords=[],
            subjects=[str(field) for field in fields_of_study][:8],
            doc_type=doc_type,
            source_score=self.source_score,
            source=self.name,
        )
