"""
Academic Provider Registry and Orchestration Hub.
Tracks status, capabilities, and coordinates multi-source academic paper searches.
"""

import concurrent.futures
import logging
from typing import Any, Dict, List, Tuple

from app.schemas.paper import Paper
from app.research.arxiv import search_arxiv
from app.research.openalex import search_openalex
from app.research.crossref import search_crossref
from app.research.semantic_scholar import search_semantic_scholar
from app.research.pubmed import search_pubmed
from app.research.providers.europe_pmc import EuropePMCProvider
from app.research.providers.dblp import DBLPProvider
from app.research.providers.zenodo import ZenodoProvider
from app.research.providers.datacite import DataCiteProvider
from app.research.providers.doaj import DOAJProvider
from app.research.providers.core import COREProvider
from app.research.providers.outbound_portals import get_outbound_academic_portals
from app.research.deduplicator import deduplicate_papers
from app.research.ranker import rank_papers

logger = logging.getLogger("researchos.registry")


class ProviderRegistry:
    def __init__(self):
        self.europe_pmc = EuropePMCProvider()
        self.dblp = DBLPProvider()
        self.zenodo = ZenodoProvider()
        self.datacite = DataCiteProvider()
        self.doaj = DOAJProvider()
        self.core = COREProvider()

        # Track observed statuses
        self.provider_statuses: Dict[str, str] = {
            "arXiv": "Connected",
            "OpenAlex": "Connected",
            "Crossref": "Connected",
            "Semantic Scholar": "Connected",
            "PubMed": "Connected",
            "Europe PMC": "Connected",
            "DBLP": "Connected",
            "Zenodo": "Connected",
            "DataCite": "Connected",
            "DOAJ": "Connected",
            "CORE": "Connected",
        }

    def get_source_coverage_report(self) -> Dict[str, Any]:
        """Return live source coverage dashboard including integrated providers and outbound portals."""
        integrated = []
        for name, status in self.provider_statuses.items():
            integrated.append({
                "name": name,
                "status": status,
                "integrated": True,
                "type": "Direct API Integration",
            })

        outbound = get_outbound_academic_portals("")
        for portal in outbound:
            integrated.append({
                "name": portal["name"],
                "status": "External Portal Available",
                "integrated": False,
                "type": "Outbound Search Link",
                "note": portal["note"],
            })

        return {
            "total_sources": len(integrated),
            "integrated_count": len(self.provider_statuses),
            "sources": integrated,
        }

    def execute_unified_search(
        self,
        query: str,
        target_count: int = 30,
    ) -> Tuple[List[Paper], List[str], List[str]]:
        """
        Execute parallel queries across all enabled academic providers.
        Returns: (ranked_papers, queried_providers, succeeded_providers)
        """
        search_functions = {
            "arXiv": lambda q: search_arxiv(q, max_results=35),
            "OpenAlex": lambda q: search_openalex(q, max_results=35),
            "Crossref": lambda q: search_crossref(q, max_results=25),
            "Semantic Scholar": lambda q: search_semantic_scholar(q, max_results=20),
            "PubMed": lambda q: search_pubmed(q, max_results=20),
            "Europe PMC": lambda q: self.europe_pmc.search(q, max_results=20),
            "DBLP": lambda q: self.dblp.search(q, max_results=20),
            "Zenodo": lambda q: self.zenodo.search(q, max_results=15),
            "DataCite": lambda q: self.datacite.search(q, max_results=15),
            "DOAJ": lambda q: self.doaj.search(q, max_results=15),
            "CORE": lambda q: self.core.search(q, max_results=15),
        }

        queried = list(search_functions.keys())
        succeeded: List[str] = []
        all_candidates: List[Paper] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_provider = {
                executor.submit(func, query): name
                for name, func in search_functions.items()
            }

            for future in concurrent.futures.as_completed(future_to_provider, timeout=25):
                provider_name = future_to_provider[future]
                try:
                    papers = future.result()
                    if papers:
                        succeeded.append(provider_name)
                        self.provider_statuses[provider_name] = "Request succeeded"
                        all_candidates.extend(papers)
                    else:
                        self.provider_statuses[provider_name] = "Connected"
                except Exception as e:
                    logger.warning("Provider %s query failed: %s", provider_name, e)
                    self.provider_statuses[provider_name] = "Temporarily unavailable"

        # Deduplicate and rank Top 30
        unique_papers = deduplicate_papers(all_candidates)
        ranked_top = rank_papers(unique_papers, query=query, limit=target_count)

        return ranked_top, queried, succeeded


# Global singleton registry
registry = ProviderRegistry()
