"""Crossref academic search provider."""

import logging
from typing import List
from urllib.parse import quote

import requests

from app.schemas.paper import Paper
from app.research.normalizer import normalize_title, clean_doi, build_paper_id

logger = logging.getLogger("researchos.crossref")

CROSSREF_API_URL = "https://api.crossref.org/works"
USER_AGENT = "ResearchOS/1.0 (https://researchos.dev; mailto:contact@researchos.dev)"
REQUEST_TIMEOUT = 12


def search_crossref(query: str, max_results: int = 30) -> List[Paper]:
    """Search Crossref for published works."""
    if not query or not query.strip():
        return []

    url = f"{CROSSREF_API_URL}?query={quote(query.strip())}&rows={max_results}&sort=relevance"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            logger.warning("Crossref returned status %s", response.status_code)
            return []
        data = response.json()
    except Exception as e:
        logger.warning("Crossref search failed: %s", e)
        return []

    items = data.get("message", {}).get("items", [])
    papers: List[Paper] = []

    for item in items:
        titles = item.get("title", [])
        if not titles or not titles[0]:
            continue
        title = normalize_title(titles[0])

        authors = []
        for author in item.get("author", []):
            given = author.get("given", "").strip()
            family = author.get("family", "").strip()
            full_name = f"{given} {family}".strip()
            if full_name:
                authors.append(full_name)

        doi = clean_doi(item.get("DOI"))
        year = None
        created_parts = item.get("published-print", {}).get("date-parts") or item.get("created", {}).get("date-parts")
        if created_parts and created_parts[0] and len(created_parts[0]) > 0:
            year = str(created_parts[0][0])

        abstract = item.get("abstract", "")
        # Remove JATS/XML markup tags if present in Crossref abstracts
        if abstract:
            import re
            abstract = re.sub(r"<[^>]+>", "", abstract)
            abstract = normalize_title(abstract)

        paper_url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
        container_title = item.get("container-title", [])
        venue = container_title[0] if container_title else None
        citations = item.get("is-referenced-by-count")

        # Find direct PDF link from resource links
        pdf_url = None
        for link in item.get("link", []):
            if "pdf" in link.get("content-type", "").lower():
                pdf_url = link.get("URL")
                break

        paper = Paper(
            id=build_paper_id("crossref", doi or title),
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            published_date=None,
            doi=doi,
            arxiv_id=None,
            paper_url=paper_url,
            pdf_url=pdf_url,
            source="Crossref",
            citation_count=citations,
            journal=venue,
            venue=venue,
            keywords=[],
        )
        papers.append(paper)

    return papers
