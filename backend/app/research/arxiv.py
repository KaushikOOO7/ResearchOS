"""
arXiv provider.

Uses the public arXiv Atom API (no key required):
``https://export.arxiv.org/api/query``

Strategy: a term-conjunctive query first (high precision), then a broader
phrase query if the first pass did not fill the requested budget. arXiv asks
clients to be polite, so at most two requests are issued and a short delay is
respected between them.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import List, Optional

from app.models.paper import Paper, QueryAnalysis
from app.research.base import ResearchSource, build_paper
from app.utils.http import ProviderError, get_text
from app.utils.logging_setup import get_logger
from app.utils.text import sanitize_external_text

logger = get_logger("arxiv")

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

# arXiv publishes ~200k papers/year; relevance search is good but noisy, so we
# fetch a generous pool and let the ranker do the work.
_MIN_TERM_QUERY_LENGTH = 2


class ArxivSource(ResearchSource):
    """arXiv preprint server (Computer Science, Physics, Maths, ...)."""

    name = "arXiv"
    tier = 3
    source_score = 82.0  # open, complete metadata; preprints are not peer-reviewed

    def fetch(self, query: str, limit: int, query_analysis: QueryAnalysis) -> List[Paper]:
        primary_query = self._build_query(query_analysis, broad=False)

        published: List[Paper] = []
        seen: set[str] = set()

        entries = self._request(primary_query, limit)
        self._collect(entries, published, seen)

        # If the precise query under-delivers, widen it once.
        if len(published) < limit:
            broad_query = self._build_query(query_analysis, broad=True)
            if broad_query and broad_query != primary_query:
                time.sleep(0.5)  # polite pacing between arXiv requests
                remaining = max(limit - len(published), min(limit, 20))
                entries = self._request(broad_query, remaining)
                self._collect(entries, published, seen)

        return published[:limit]

    # ------------------------------------------------------------------
    # Query construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_query(query_analysis: QueryAnalysis, broad: bool) -> str:
        """
        Build an arXiv ``search_query`` expression.

        Precise form: ``all:"term1" AND all:"term2" ...``
        Broad form:   ``all:"multi word phrase"`` / ``all:term1 OR all:term2``
        """
        terms = [t for t in query_analysis.terms if len(t) > 1]
        phrases = query_analysis.phrases

        if not broad and len(terms) >= _MIN_TERM_QUERY_LENGTH:
            chosen = terms[:6]
            return " AND ".join(f'all:"{term}"' for term in chosen)

        if phrases:
            phrase = max(phrases, key=lambda p: len(p.split()))
            return f'all:"{phrase}"'

        if terms:
            return " OR ".join(f'all:"{term}"' for term in terms[:6])

        return ""

    def _request(self, search_query: str, max_results: int) -> List[ET.Element]:
        if not search_query:
            return []

        text = get_text(
            self.name,
            ARXIV_API_URL,
            params={
                "search_query": search_query,
                "start": 0,
                "max_results": max(1, min(max_results, 100)),
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
        )

        if "<entry" not in text:
            # arXiv returns a plain-text error page (often 503 "try again")
            # with HTTP 200; treat it as a provider failure.
            if "Error" in text or "error" in text:
                raise ProviderError(self.name, "arXiv returned an error response")

        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise ProviderError(self.name, "could not parse arXiv Atom response") from exc

        return root.findall("atom:entry", ATOM_NS)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _collect(self, entries: List[ET.Element], target: List[Paper], seen: set[str]) -> None:
        for entry in entries:
            paper = self._parse_entry(entry)
            if not paper or not paper.title:
                continue
            dedupe_key = paper.arxiv_id or paper.doi or paper.title.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            target.append(paper)

    def _parse_entry(self, entry: ET.Element) -> Optional[Paper]:
        def find_text(path: str) -> Optional[str]:
            node = entry.find(path, ATOM_NS)
            if node is None or node.text is None:
                return None
            return sanitize_external_text(node.text, max_chars=2000)

        title = find_text("atom:title") or ""
        abstract = find_text("atom:summary") or ""

        published = find_text("atom:published") or ""
        year = int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None

        abs_url = find_text("atom:id") or ""
        arxiv_id = abs_url.split("/abs/")[-1] if "/abs/" in abs_url else abs_url

        pdf_url = None
        for link in entry.findall("atom:link", ATOM_NS):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href")
                break
        if not pdf_url and arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

        authors = []
        for author in entry.findall("atom:author", ATOM_NS):
            name = author.find("atom:name", ATOM_NS)
            if name is not None and name.text:
                authors.append(sanitize_external_text(name.text, max_chars=120))

        doi = find_text("arxiv:doi")
        journal_ref = find_text("arxiv:journal_ref")
        primary_category = entry.find("arxiv:primary_category", ATOM_NS)
        subjects = []
        if primary_category is not None:
            term = primary_category.attrib.get("term")
            if term:
                subjects.append(term)
        for category in entry.findall("atom:category", ATOM_NS):
            term = category.attrib.get("term")
            if term and term not in subjects:
                subjects.append(term)

        comment = find_text("arxiv:comment")
        doc_type = "preprint"
        if journal_ref:
            doc_type = "journal-article"

        keywords = []
        if comment:
            keywords.append(comment)

        return build_paper(
            title=title,
            abstract=abstract,
            authors=authors,
            year=year,
            doi=doi,
            arxiv_id=arxiv_id,
            venue=journal_ref or "arXiv (preprint)",
            paper_url=abs_url or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None),
            pdf_url=pdf_url,
            citation_count=None,  # arXiv exposes no citation counts
            is_open_access=True,
            keywords=keywords,
            subjects=subjects,
            doc_type=doc_type,
            source_score=self.source_score,
            source=self.name,
        )
