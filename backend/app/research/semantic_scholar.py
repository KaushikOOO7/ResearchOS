"""Semantic Scholar academic search provider."""

import logging
from typing import List
from urllib.parse import quote

import requests

from app.schemas.paper import Paper
from app.research.normalizer import normalize_title, clean_doi, clean_arxiv_id, build_paper_id

logger = logging.getLogger("researchos.semanticscholar")

S2_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
USER_AGENT = "ResearchOS/1.0 (academic-platform; contact@researchos.dev)"
REQUEST_TIMEOUT = 12


def search_semantic_scholar(query: str, max_results: int = 25) -> List[Paper]:
    """Search Semantic Scholar with fields for citations, openAccessPdf, and abstract."""
    if not query or not query.strip():
        return []

    fields = "title,authors,year,abstract,citationCount,url,openAccessPdf,externalIds,venue"
    url = f"{S2_API_URL}?query={quote(query.strip())}&limit={max_results}&fields={fields}"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            logger.warning("Semantic Scholar returned status %s", response.status_code)
            return []
        data = response.json()
    except Exception as e:
        logger.warning("Semantic Scholar request failed: %s", e)
        return []

    items = data.get("data", [])
    papers: List[Paper] = []

    for item in items:
        title = normalize_title(item.get("title") or "")
        if not title:
            continue

        authors = [a.get("name").strip() for a in item.get("authors", []) if a.get("name")]
        year = str(item.get("year")) if item.get("year") else None
        abstract = normalize_title(item.get("abstract") or "")
        citations = item.get("citationCount")

        ext_ids = item.get("externalIds") or {}
        doi = clean_doi(ext_ids.get("DOI"))
        arxiv_id = clean_arxiv_id(ext_ids.get("ArXiv"))

        oa_pdf = item.get("openAccessPdf") or {}
        pdf_url = oa_pdf.get("url")
        paper_url = item.get("url") or (f"https://doi.org/{doi}" if doi else "")
        venue = item.get("venue")

        s2_id = item.get("paperId", "")

        paper = Paper(
            id=build_paper_id("s2", s2_id or doi or title),
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            published_date=None,
            doi=doi,
            arxiv_id=arxiv_id,
            paper_url=paper_url,
            pdf_url=pdf_url,
            source="Semantic Scholar",
            citation_count=citations,
            journal=venue,
            venue=venue,
            keywords=[],
        )
        papers.append(paper)

    return papers
