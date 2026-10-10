from app.research.engine import execute_multi_provider_search
from app.research.arxiv import search_arxiv
from app.research.deduplicator import deduplicate_papers
from app.research.ranker import rank_papers, compute_paper_score

__all__ = [
    "execute_multi_provider_search",
    "search_arxiv",
    "deduplicate_papers",
    "rank_papers",
    "compute_paper_score",
]
