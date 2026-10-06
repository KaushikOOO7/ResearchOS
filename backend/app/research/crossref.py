"""
Crossref provider.

Crossref is the authoritative registry of DOIs, which makes it the best
source for *published* (non-preprint) records: journal articles, conference
proceedings and book chapters with verified bibliographic metadata.

Docs: https://api.crossref.org/swagger-ui/index.html
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.paper import Paper, QueryAnalysis
from app.research.base import ResearchSource, build_paper
from app.utils.http import ProviderError, get_json
from app.utils.logging_setup import get_logger

logger = get_logger("crossref")

CROSSREF_API_URL = "https://api.crossref.org/works"

_SELECT_FIELDS = ",".join(
    [
        "DOI",
        "title",
        "author",
        "issued",
        "abstract",
        "container-title",
        "short-container-title",
        "is-referenced-by-count",
        "type",
        "URL",
        "link",
        "subject",
        "publisher",
    ]
)

#: Crossref record types that are not research papers.
_EXCLUDED_TYPES = {"component", "dataset", "peer-review", "grant", "journal", "journal-issue"}


class CrossrefSource(ResearchSource):
    """Crossref DOI registry."""

    name = "Crossref"
    tier = 1
    source_score = 88.0

    def fetch(self, query: str, limit: int, query_analysis: QueryAnalysis) -> List[Paper]:
        params: Dict[str, Any] = {
            "query.bibliographic": query,
            "rows": max(1, min(limit, 100)),
            "select": _SELECT_FIELDS,
            "sort": "relevance",
            "order": "desc",
        }
        if settings.crossref_email:
            params["mailto"] = settings.crossref_email

        payload = get_json(self.name, CROSSREF_API_URL, params=params)

        message = (payload or {}).get("message") or {}
        items = message.get("items")
        if items is None:
            raise ProviderError(self.name, "unexpected response shape")

        papers: List[Paper] = []
        for item in items:
            paper = self._parse_item(item)
            if paper and paper.title:
                papers.append(paper)
        return papers

    def _parse_item(self, item: Dict[str, Any]) -> Optional[Paper]:
        if not isinstance(item, dict):
            return None

        doc_type = item.get("type")
        if doc_type in _EXCLUDED_TYPES:
            return None

        title_list = item.get("title") or []
        title = title_list[0] if isinstance(title_list, list) and title_list else str(title_list or "")

        container = item.get("container-title") or []
        venue = container[0] if isinstance(container, list) and container else None

        year = self._extract_year(item)
        published_date = self._extract_date_parts(item)

        authors: List[str] = []
        for author in item.get("author") or []:
            if not isinstance(author, dict):
                continue
            if author.get("name"):
                authors.append(author["name"])
                continue
            given = author.get("given") or ""
            family = author.get("family") or ""
            full = f"{given} {family}".strip()
            if full:
                authors.append(full)

        pdf_url = None
        for link in item.get("link") or []:
            if not isinstance(link, dict):
                continue
            if link.get("content-type") == "application/pdf" and link.get("URL"):
                pdf_url = link["URL"]
                break

        citations = item.get("is-referenced-by-count")
        if not isinstance(citations, int):
            citations = None

        subjects = item.get("subject") or []
        keywords = subjects if isinstance(subjects, list) else []

        return build_paper(
            title=title,
            abstract=item.get("abstract") or "",
            authors=authors,
            year=year,
            published_date=published_date or year,
            doi=item.get("DOI"),
            venue=venue or item.get("publisher"),
            journal=venue or None,
            paper_url=item.get("URL") or (
                f"https://doi.org/{item['DOI']}" if item.get("DOI") else None
            ),
            pdf_url=pdf_url,
            citation_count=citations,
            is_open_access=bool(pdf_url) if pdf_url else None,
            keywords=keywords,
            subjects=[],
            doc_type=doc_type,
            source_score=self.source_score,
            source=self.name,
        )

    @staticmethod
    def _extract_date_parts(item: Dict[str, Any]) -> Optional[str]:
        """Return the raw ``date-parts`` array for the best available date key."""
        for key in ("issued", "published-print", "published-online", "published"):
            node = item.get(key)
            if isinstance(node, dict) and node.get("date-parts"):
                return node["date-parts"]  # normalizer converts [Y, M, D]
        return None

    @staticmethod
    def _extract_year(item: Dict[str, Any]) -> Optional[int]:
        """Crossref dates are ``{'date-parts': [[2021, 5, 12]]}``."""
        for key in ("issued", "published-print", "published-online", "published", "created"):
            node = item.get(key)
            if not isinstance(node, dict):
                continue
            parts = node.get("date-parts")
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                year = parts[0][0]
                if isinstance(year, int):
                    return year
        return None
