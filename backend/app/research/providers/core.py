"""CORE open access repository provider."""

import logging
import os
from typing import List
from urllib.parse import quote
import requests

from app.schemas.paper import Paper
from app.research.normalizer import normalize_title, clean_doi, build_paper_id
from app.research.providers.base import BaseProvider

logger = logging.getLogger("researchos.core")

CORE_API = "https://api.core.ac.uk/v3/search/works"
USER_AGENT = "ResearchOS/1.0 (academic-intelligence; contact@researchos.dev)"


class COREProvider(BaseProvider):
    def __init__(self):
        has_key = bool(os.getenv("CORE_API_KEY", "").strip())
        super().__init__(
            name="CORE",
            website="https://core.ac.uk",
            requires_auth=False,
            default_enabled=True,
        )

    def search(self, query: str, max_results: int = 20) -> List[Paper]:
        if not query or not query.strip():
            return []

        url = f"{CORE_API}?q={quote(query.strip())}&limit={max_results}"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        api_key = os.getenv("CORE_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                self.last_status = "Connected"
                data = res.json()
            elif res.status_code in (401, 403):
                self.last_status = "Authentication required"
                return []
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

        results = data.get("results", [])
        papers: List[Paper] = []

        for item in results:
            title = normalize_title(item.get("title") or "")
            if not title:
                continue

            authors = [a.get("name", "").strip() for a in item.get("authors", []) if a.get("name")]
            year = str(item.get("yearPublished")) if item.get("yearPublished") else None
            doi = clean_doi(item.get("doi"))
            abstract = normalize_title(item.get("abstract") or "")
            download_url = item.get("downloadUrl")

            paper_url = item.get("sourceFulltextUrls", [None])[0] or (f"https://doi.org/{doi}" if doi else "")

            papers.append(
                Paper(
                    id=build_paper_id("core", str(item.get("id")) or doi or title),
                    title=title,
                    authors=authors[:5],
                    abstract=abstract,
                    year=year,
                    published_date=None,
                    doi=doi,
                    arxiv_id=None,
                    paper_url=paper_url,
                    pdf_url=download_url,
                    source="CORE",
                    citation_count=item.get("citationCount"),
                    journal=item.get("publisher"),
                    venue="CORE Repository",
                    keywords=[],
                )
            )

        return papers
