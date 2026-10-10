"""OpenAlex academic search provider."""

import logging
from typing import List
from urllib.parse import quote

import requests

from app.schemas.paper import Paper
from app.research.normalizer import normalize_title, clean_doi, build_paper_id

logger = logging.getLogger("researchos.openalex")

OPENALEX_API_URL = "https://api.openalex.org/works"
USER_AGENT = "ResearchOS/1.0 (academic-intelligence-platform; mailto:contact@researchos.dev)"
REQUEST_TIMEOUT = 12


def search_openalex(query: str, max_results: int = 30) -> List[Paper]:
    """Search OpenAlex for scholarly works with real citation data."""
    if not query or not query.strip():
        return []

    url = (
        f"{OPENALEX_API_URL}"
        f"?search={quote(query.strip())}"
        f"&per-page={max_results}"
        f"&select=id,title,publication_year,publication_date,doi,primary_location,authorships,abstract_inverted_index,cited_by_count,concepts"
    )

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            logger.warning("OpenAlex returned status code %s", response.status_code)
            return []
        data = response.json()
    except Exception as e:
        logger.warning("OpenAlex search failed: %s", e)
        return []

    results = data.get("results", [])
    papers: List[Paper] = []

    for item in results:
        title = normalize_title(item.get("title") or "")
        if not title:
            continue

        # Reconstruct abstract from inverted index if present
        abstract = ""
        inv_index = item.get("abstract_inverted_index")
        if inv_index and isinstance(inv_index, dict):
            words = []
            for word, positions in inv_index.items():
                for pos in positions:
                    words.append((pos, word))
            words.sort(key=lambda x: x[0])
            abstract = " ".join([w[1] for w in words])

        authors = []
        for authorship in item.get("authorships", []):
            author_obj = authorship.get("author", {})
            name = author_obj.get("display_name")
            if name:
                authors.append(name.strip())

        year = str(item.get("publication_year")) if item.get("publication_year") else None
        doi = clean_doi(item.get("doi"))
        citations = item.get("cited_by_count")

        primary_loc = item.get("primary_location") or {}
        pdf_url = primary_loc.get("pdf_url")
        paper_url = primary_loc.get("landing_page_url") or (f"https://doi.org/{doi}" if doi else item.get("id", ""))
        source_venue = primary_loc.get("source", {}).get("display_name") if primary_loc.get("source") else None

        keywords = [c.get("display_name") for c in item.get("concepts", []) if c.get("display_name")]

        openalex_id = item.get("id", "").split("/")[-1]

        paper = Paper(
            id=build_paper_id("openalex", openalex_id or doi or title),
            title=title,
            authors=authors,
            abstract=normalize_title(abstract),
            year=year,
            published_date=item.get("publication_date"),
            doi=doi,
            arxiv_id=None,
            paper_url=paper_url,
            pdf_url=pdf_url,
            source="OpenAlex",
            citation_count=citations,
            journal=source_venue,
            venue=source_venue,
            keywords=keywords[:5],
        )
        papers.append(paper)

    return papers
