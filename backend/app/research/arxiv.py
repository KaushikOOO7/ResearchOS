"""arXiv academic paper search provider."""

import logging
import time
import xml.etree.ElementTree as ET
from typing import List
from urllib.parse import quote

import requests

from app.schemas.paper import Paper
from app.research.normalizer import normalize_title, clean_arxiv_id, build_paper_id

logger = logging.getLogger("researchos.arxiv")

ARXIV_API_URL = "https://export.arxiv.org/api/query"
USER_AGENT = "ResearchOS/1.0 (academic-intelligence-platform; mailto:contact@researchos.dev)"
REQUEST_TIMEOUT = 15


def search_arxiv(query: str, max_results: int = 35) -> List[Paper]:
    """
    Search arXiv for research papers matching query.
    Returns normalized Paper objects.
    """
    if not query or not query.strip():
        return []

    encoded_query = quote(query.strip())
    url = (
        f"{ARXIV_API_URL}"
        f"?search_query=all:{encoded_query}"
        f"&start=0"
        f"&max_results={max_results}"
        f"&sortBy=relevance"
        f"&sortOrder=descending"
    )

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/atom+xml",
    }

    response_text = None
    # 2 retry attempts for transient arXiv hiccups
    for attempt in range(2):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                response_text = response.text
                break
            elif response.status_code in (429, 503):
                logger.warning("arXiv rate-limit / unavailable (%s), retrying...", response.status_code)
                time.sleep(1.5)
            else:
                logger.warning("arXiv returned status %s", response.status_code)
                break
        except requests.exceptions.RequestException as e:
            logger.warning("arXiv request error (attempt %d): %s", attempt + 1, e)
            time.sleep(1.0)

    if not response_text:
        return []

    try:
        root = ET.fromstring(response_text)
    except ET.ParseError as e:
        logger.error("Failed to parse arXiv Atom XML: %s", e)
        return []

    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    papers: List[Paper] = []

    for entry in root.findall("atom:entry", namespace):
        title_elem = entry.find("atom:title", namespace)
        summary_elem = entry.find("atom:summary", namespace)
        published_elem = entry.find("atom:published", namespace)
        id_elem = entry.find("atom:id", namespace)

        title = normalize_title(title_elem.text if title_elem is not None and title_elem.text else "")
        abstract = normalize_title(summary_elem.text if summary_elem is not None and summary_elem.text else "")
        published_str = published_elem.text.strip() if published_elem is not None and published_elem.text else ""
        year = published_str[:4] if published_str else None
        paper_url = id_elem.text.strip() if id_elem is not None and id_elem.text else ""

        if not title:
            continue

        authors = []
        for author in entry.findall("atom:author", namespace):
            name = author.find("atom:name", namespace)
            if name is not None and name.text:
                authors.append(name.text.strip())

        arxiv_id = clean_arxiv_id(paper_url.split("/abs/")[-1] if "/abs/" in paper_url else paper_url)
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None

        # Categories / keywords
        keywords = []
        for cat in entry.findall("atom:category", namespace):
            term = cat.get("term")
            if term:
                keywords.append(term)

        paper = Paper(
            id=build_paper_id("arxiv", arxiv_id or paper_url or title),
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            published_date=published_str[:10] if published_str else None,
            doi=None,
            arxiv_id=arxiv_id,
            paper_url=paper_url,
            pdf_url=pdf_url,
            source="arXiv",
            citation_count=None,
            journal="arXiv preprint",
            venue="arXiv",
            keywords=keywords,
        )
        papers.append(paper)

    return papers
