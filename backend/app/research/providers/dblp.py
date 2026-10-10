"""DBLP computer science bibliography provider."""

import logging
from typing import List
from urllib.parse import quote
import requests

from app.schemas.paper import Paper
from app.research.normalizer import normalize_title, clean_doi, build_paper_id
from app.research.providers.base import BaseProvider

logger = logging.getLogger("researchos.dblp")

DBLP_SEARCH_API = "https://dblp.org/search/publ/api"
USER_AGENT = "ResearchOS/1.0 (academic-intelligence; contact@researchos.dev)"


class DBLPProvider(BaseProvider):
    def __init__(self):
        super().__init__(
            name="DBLP",
            website="https://dblp.org",
            requires_auth=False,
            default_enabled=True,
        )

    def search(self, query: str, max_results: int = 25) -> List[Paper]:
        if not query or not query.strip():
            return []

        url = f"{DBLP_SEARCH_API}?q={quote(query.strip())}&format=json&h={max_results}"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                self.last_status = "Connected"
                data = res.json()
            elif res.status_code == 429:
                self.last_status = "Rate limit reached"
                return []
            else:
                self.last_status = "Request failed"
                return []
        except Exception as e:
            self.last_status = "Request failed"
            self.last_error = str(e)
            return []

        hits = data.get("result", {}).get("hits", {}).get("hit", [])
        papers: List[Paper] = []

        for hit in hits:
            info = hit.get("info", {})
            title = normalize_title(info.get("title") or "")
            if not title:
                continue

            authors_info = info.get("authors", {}).get("author", [])
            if isinstance(authors_info, dict):
                authors = [authors_info.get("text", "").strip()]
            elif isinstance(authors_info, list):
                authors = [a.get("text", "").strip() for a in authors_info if isinstance(a, dict)]
            else:
                authors = []

            year = str(info.get("year")) if info.get("year") else None
            venue = info.get("venue")
            doi = clean_doi(info.get("doi"))
            paper_url = info.get("ee") or (f"https://doi.org/{doi}" if doi else info.get("url", ""))

            papers.append(
                Paper(
                    id=build_paper_id("dblp", doi or info.get("key") or title),
                    title=title,
                    authors=authors,
                    abstract="",
                    year=year,
                    published_date=None,
                    doi=doi,
                    arxiv_id=None,
                    paper_url=paper_url,
                    pdf_url=None,
                    source="DBLP",
                    citation_count=None,
                    journal=venue,
                    venue=venue,
                    keywords=[],
                )
            )

        return papers
