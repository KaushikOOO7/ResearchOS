"""DataCite research outputs and dataset provider."""

import logging
from typing import List
from urllib.parse import quote
import requests

from app.schemas.paper import Paper
from app.research.normalizer import normalize_title, clean_doi, build_paper_id
from app.research.providers.base import BaseProvider

logger = logging.getLogger("researchos.datacite")

DATACITE_API = "https://api.datacite.org/dois"
USER_AGENT = "ResearchOS/1.0 (academic-intelligence; contact@researchos.dev)"


class DataCiteProvider(BaseProvider):
    def __init__(self):
        super().__init__(
            name="DataCite",
            website="https://datacite.org",
            requires_auth=False,
            default_enabled=True,
        )

    def search(self, query: str, max_results: int = 20) -> List[Paper]:
        if not query or not query.strip():
            return []

        url = f"{DATACITE_API}?query={quote(query.strip())}&page[size]={max_results}"
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

        items = data.get("data", [])
        papers: List[Paper] = []

        for item in items:
            attr = item.get("attributes", {})
            titles = attr.get("titles", [])
            title = normalize_title(titles[0].get("title") if titles and isinstance(titles[0], dict) else "")
            if not title:
                continue

            creators = attr.get("creators", [])
            authors = [c.get("name", "").strip() for c in creators if isinstance(c, dict) and c.get("name")]

            year = str(attr.get("publicationYear")) if attr.get("publicationYear") else None
            doi = clean_doi(attr.get("doi"))
            descriptions = attr.get("descriptions", [])
            abstract = ""
            if descriptions and isinstance(descriptions[0], dict):
                abstract = normalize_title(descriptions[0].get("description") or "")

            paper_url = attr.get("url") or (f"https://doi.org/{doi}" if doi else "")
            resource_type = attr.get("types", {}).get("resourceTypeGeneral", "DataCite Record")

            papers.append(
                Paper(
                    id=build_paper_id("datacite", doi or title),
                    title=title,
                    authors=authors[:5],
                    abstract=abstract[:800],
                    year=year,
                    published_date=None,
                    doi=doi,
                    arxiv_id=None,
                    paper_url=paper_url,
                    pdf_url=None,
                    source="DataCite",
                    citation_count=attr.get("citationCount"),
                    journal=resource_type,
                    venue=resource_type,
                    keywords=[],
                )
            )

        return papers
