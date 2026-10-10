"""Zenodo research outputs and dataset provider."""

import logging
from typing import List
from urllib.parse import quote
import requests

from app.schemas.paper import Paper
from app.research.normalizer import normalize_title, clean_doi, build_paper_id
from app.research.providers.base import BaseProvider

logger = logging.getLogger("researchos.zenodo")

ZENODO_API = "https://zenodo.org/api/records"
USER_AGENT = "ResearchOS/1.0 (academic-intelligence; contact@researchos.dev)"


class ZenodoProvider(BaseProvider):
    def __init__(self):
        super().__init__(
            name="Zenodo",
            website="https://zenodo.org",
            requires_auth=False,
            default_enabled=True,
        )

    def search(self, query: str, max_results: int = 20) -> List[Paper]:
        if not query or not query.strip():
            return []

        url = f"{ZENODO_API}?q={quote(query.strip())}&size={max_results}&sort=bestmatch"
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

        hits = data.get("hits", {}).get("hits", [])
        papers: List[Paper] = []

        for hit in hits:
            metadata = hit.get("metadata", {})
            title = normalize_title(metadata.get("title") or "")
            if not title:
                continue

            creators = metadata.get("creators", [])
            authors = [c.get("name", "").strip() for c in creators if c.get("name")]

            year = None
            pub_date = metadata.get("publication_date")
            if pub_date:
                year = str(pub_date)[:4]

            doi = clean_doi(hit.get("doi") or metadata.get("doi"))
            abstract = normalize_title(metadata.get("description") or "")
            # Remove html tags if present in Zenodo descriptions
            import re
            abstract = re.sub(r"<[^>]+>", " ", abstract)

            links = hit.get("links", {})
            paper_url = links.get("html") or (f"https://doi.org/{doi}" if doi else "")
            
            # Check for direct pdf in files
            pdf_url = None
            for f in hit.get("files", []):
                if f.get("key", "").endswith(".pdf") or "pdf" in f.get("type", "").lower():
                    pdf_url = f.get("links", {}).get("self")
                    break

            resource_type = metadata.get("resource_type", {}).get("title", "Zenodo Record")

            papers.append(
                Paper(
                    id=build_paper_id("zenodo", str(hit.get("id")) or doi or title),
                    title=title,
                    authors=authors[:5],
                    abstract=abstract[:800],
                    year=year,
                    published_date=pub_date,
                    doi=doi,
                    arxiv_id=None,
                    paper_url=paper_url,
                    pdf_url=pdf_url,
                    source="Zenodo",
                    citation_count=None,
                    journal=resource_type,
                    venue="Zenodo",
                    keywords=[metadata.get("resource_type", {}).get("type", "")],
                )
            )

        return papers
