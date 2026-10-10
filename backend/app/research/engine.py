"""
Multi-provider academic search engine orchestrator.
Delegates to ProviderRegistry for unified search across all major academic repositories.
"""

from typing import Any, Dict, List, Tuple
from app.schemas.paper import Paper
from app.research.providers.provider_registry import registry
from app.research.providers.outbound_portals import get_outbound_academic_portals


def execute_multi_provider_search(
    query: str,
    target_count: int = 30
) -> Tuple[List[Paper], List[str], List[str]]:
    """
    Search academic providers in parallel with timeout tolerance.
    Returns: (ranked_top_papers, providers_queried, providers_succeeded)
    """
    return registry.execute_unified_search(query, target_count=target_count)


def get_source_coverage(query: str = "") -> Dict[str, Any]:
    """Return live status of integrated providers and outbound academic portals."""
    report = registry.get_source_coverage_report()
    if query:
        report["outbound_portals"] = get_outbound_academic_portals(query)
    return report
