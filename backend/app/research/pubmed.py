"""PubMed biomedical academic search provider."""

import logging
import xml.etree.ElementTree as ET
from typing import List
from urllib.parse import quote

import requests

from app.schemas.paper import Paper
from app.research.normalizer import normalize_title, clean_doi, build_paper_id

logger = logging.getLogger("researchos.pubmed")

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
USER_AGENT = "ResearchOS/1.0 (contact@researchos.dev)"
REQUEST_TIMEOUT = 12


def search_pubmed(query: str, max_results: int = 20) -> List[Paper]:
    """Search PubMed using NCBI E-utilities."""
    if not query or not query.strip():
        return []

    # 1. Search for IDs
    search_params = {
        "db": "pubmed",
        "term": query.strip(),
        "retmax": str(max_results),
        "retmode": "json",
        "sort": "relevance",
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        search_res = requests.get(ESEARCH_URL, params=search_params, headers=headers, timeout=REQUEST_TIMEOUT)
        if search_res.status_code != 200:
            return []
        search_data = search_res.json()
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []
    except Exception as e:
        logger.warning("PubMed ID search failed: %s", e)
        return []

    # 2. Fetch Summaries
    summary_params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "json",
    }

    try:
        summary_res = requests.get(ESUMMARY_URL, params=summary_params, headers=headers, timeout=REQUEST_TIMEOUT)
        if summary_res.status_code != 200:
            return []
        summary_data = summary_res.json()
        result_dict = summary_data.get("result", {})
    except Exception as e:
        logger.warning("PubMed summary fetch failed: %s", e)
        return []

    papers: List[Paper] = []
    for pmid in id_list:
        doc = result_dict.get(pmid)
        if not doc or not isinstance(doc, dict):
            continue

        title = normalize_title(doc.get("title") or "")
        if not title:
            continue

        authors = [a.get("name").strip() for a in doc.get("authors", []) if a.get("name")]
        pubdate = doc.get("pubdate", "")
        year = pubdate[:4] if len(pubdate) >= 4 and pubdate[:4].isdigit() else None

        source_venue = doc.get("source")
        paper_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        # Check for DOI in articleids
        doi = None
        for aid in doc.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi = clean_doi(aid.get("value"))
                break

        paper = Paper(
            id=build_paper_id("pubmed", pmid),
            title=title,
            authors=authors,
            abstract="",  # Summary endpoint does not return full abstract
            year=year,
            published_date=pubdate,
            doi=doi,
            arxiv_id=None,
            paper_url=paper_url,
            pdf_url=None,
            source="PubMed",
            citation_count=None,
            journal=source_venue,
            venue=source_venue,
            keywords=[],
        )
        papers.append(paper)

    return papers
