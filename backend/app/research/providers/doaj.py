"""DOAJ open access journal provider."""

import logging
from typing import List
from urllib.parse import quote
import requests

from app.schemas.paper import Paper
from app.research.normalizer import normalize_title, clean_doi, build_paper_id
from app.research.providers.base import BaseProvider

logger = logging.getLogger("researchos.doaj")

DOAJ_API = "https://doaj.org/api/search/articles"
USER_AGENT = "ResearchOS/1.0 (academic-intelligence; contact@researchos.dev)"


class DOAJProvider(BaseProvider):
    def __init__(self):
        super().__init__(
            name="DOAJ",
            website="https://doaj.org",
            requires_auth=False,
            default_enabled=True,
        )

    def search(self, query: str, max_results: int = 20) -> List[Paper]:
        if not query or not query.strip():
            return []

        url = f"{DOAJ_API}/{quote(query.strip())}?pageSize={max_results}"
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

        results = data.get("results", [])
        papers: List[Paper] = []

        for item in results:
            bib = item.get("bibjson", {})
            title = normalize_title(bib.get("title") or "")
            if not title:
                continue

            authors = [a.get("name", "").strip() for a in bib.get("author", []) if a.get("name")]
            year = str(bib.get("year")) if bib.get("year") else None
            abstract = normalize_title(bib.get("abstract") or "")
            journal = bib.get("journal", {}).get("title")

            doi = None
            for identifier in bib.get("identifier", []):
                if identifier.get("type", "").lower() == "doi":
                    doi = clean_doi(identifier.get("id"))
                    break

            paper_url = ""
            pdf_url = None
            for link in bib.get("link", []):
                url_val = link.get("url")
                if link.get("type") == "fulltext":
                    if url_val and url_val.endswith(".pdf"):
                        pdf_url = url_val
                    else:
                        paper_url = url_val

            if not paper_url and doi:
                paper_url = f"https://doi.org/{doi}"

            papers.append(
                Paper(
                    id=build_paper_id("doaj", doi or title),
                    title=title,
                    authors=authors[:5],
                    abstract=abstract,
                    year=year,
                    published_date=None,
                    doi=doi,
                    arxiv_id=None,
                    paper_url=paper_url,
                    pdf_url=pdf_url,
                    source="DOAJ",
                    citation_count=None,
                    journal=journal,
                    venue=journal,
                    keywords=bib.get("keywords", [])[:4],
                )
            )

        return papers
