"""
In-memory paper store.

Papers returned by ``POST /research`` are remembered so that
``GET /papers/{paper_id}`` can serve the paper detail view without a database.
Entries expire automatically (TTL) and the store is bounded in size.

This is deliberately a thin interface: when Phase 7 adds PostgreSQL, only
this module changes.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.models.paper import Paper
from app.services.cache import TTLCache

_store: TTLCache = TTLCache(max_entries=64, ttl_seconds=6 * 60 * 60)


def remember_papers(papers: List[Paper]) -> None:
    """Index a list of papers by id for later lookup."""
    for paper in papers:
        if paper.id:
            _store.set(paper.id, paper.to_public_dict())


def get_paper(paper_id: str) -> Optional[Dict]:
    """Return a previously seen paper, or ``None``."""
    return _store.get(paper_id)


def store_stats() -> Dict:
    """Sizing info for diagnostics."""
    return _store.stats()
