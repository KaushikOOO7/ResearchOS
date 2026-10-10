"""Europe PMC academic search provider."""

import logging
from typing import List
from urllib.parse import quote
import requests

from app.schemas.paper import Paper
from app.research.normalizer import normalize_title, clean_doi, build_paper_id
from app.research.providers.base import BaseProvider

logger = logging.getLogger("researchos.europe_pmc")

EUROPE_PMC_API = "https://europepmc.org/RestfulWebService/rest/search"
USER_AGENT = "ResearchOS/1.0 (academic-intelligence-platform; contact@researchos.dev)"


class EuropePMCProvider(BaseProvider):
    def __init__(self):
        super().__init__(
            name="Europe PMC",
            website="https://europepmc.org",
            requires_auth=False,
            default_enabled=True,
        )

    def search(self, query: str, max_results: int = 25) -> List[Paper]:
        if not query or not query.strip():
            return []

        url = f"{EUROPE_PMC_API}?query={quote(query.strip())}&format=json&pageSize={max_results}&resultType=core"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

        try:
            response = requests.get(url, headers=headers, timeout=12)
            if response.status_code == 200:
                self.last_status = "Connected"
                data = response.json()
            elif response.status_code == 429:
                self.last_status = "Rate limit reached"
                return []
            else:
                self.last_status = "Request failed"
                return []
        except Exception as e:
            self.last_status = "Request failed"
            self.last_error = str(e)
            return []

        results = data.get("resultList", {}).get("result", [])
        papers: List[Paper] = []

        for item in results:
            title = normalize_title(item.get("title") or "")
            if not title:
                continue

            authors_str = item.get("authorString", "")
            authors = [a.strip() for a in authors_str.split(",") if a.strip()] if authors_str else []

            year = str(item.get("pubYear")) if item.get("pubYear") else None
            doi = clean_doi(item.get("doi"))
            pmid = item.get("pmid")
            pmcid = item.get("pmcid")
            abstract = normalize_title(item.get("abstractText") or "")
            journal = item.get("journalTitle")
            citations = item.get("citedByCount")

            pdf_url = f"https://europepmc.org/articles/{pmcid}?pdf=render" if pmcid else None
            paper_url = f"https://europepmc.org/article/MED/{pmid}" if pmid else (f"https://doi.org/{doi}" if doi else "")

            papers.append(
                Paper(
                    id=build_paper_id("europepmc", pmcid or pmid or doi or title),
                    title=title,
                    authors=authors[:6],
                    abstract=abstract,
                    year=year,
                    published_date=None,
                    doi=doi,
                    arxiv_id=None,
                    paper_url=paper_url,
                    pdf_url=pdf_url,
                    source="Europe PMC",
                    citation_count=citations,
                    journal=journal,
                    venue=journal,
                    keywords=[],
                )
            )

        return papers
