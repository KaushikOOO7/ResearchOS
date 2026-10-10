"""
Paper relevance scoring and ranking engine.

Ranking algorithm weights:
1. Textual relevance (50%):
   - Exact phrase match in title (bonus +30)
   - Query token occurrences in title (each +10)
   - Query token occurrences in abstract (each +2, capped at +10)
2. Citation impact (25%):
   - Real citation count log-scaled: log10(citations + 1) * 5 (capped at +25)
3. Recency signal (15%):
   - Current year (2026/2025): +15
   - 2024: +12, 2023: +9, 2022: +6, older: proportional decay
4. Accessibility signal (10%):
   - Direct PDF URL availability (+10)
"""

import math
import re
from datetime import datetime
from typing import List, Set
from app.schemas.paper import Paper


def _extract_query_tokens(query: str) -> List[str]:
    """Tokenize query into search terms, ignoring short stop words."""
    words = re.findall(r"[a-zA-Z0-9]{2,}", query.lower())
    stop_words = {"the", "and", "for", "with", "from", "that", "this", "via", "what", "how", "why"}
    return [w for w in words if w not in stop_words] or words


def compute_paper_score(paper: Paper, query: str, current_year: int = 2026) -> float:
    """
    Calculate deterministic relevance score for a paper based on query match,
    citations, recency, and PDF accessibility.
    """
    score = 0.0
    query_lower = query.lower().strip()
    query_tokens = _extract_query_tokens(query)

    title_lower = (paper.title or "").lower()
    abstract_lower = (paper.abstract or "").lower()

    # 1. Title matching
    # Exact phrase match in title
    if query_lower and query_lower in title_lower:
        score += 30.0

    # Token matches in title
    title_matches = sum(1 for token in query_tokens if token in title_lower)
    score += title_matches * 10.0

    # 2. Abstract matching
    abstract_matches = sum(1 for token in query_tokens if token in abstract_lower)
    score += min(abstract_matches * 2.0, 10.0)

    # 3. Citation impact (only if real citation data exists)
    if paper.citation_count is not None and paper.citation_count > 0:
        # log10(1) = 0, log10(10) = 1, log10(100) = 2, log10(1000) = 3
        citation_score = math.log10(paper.citation_count + 1) * 6.0
        score += min(citation_score, 25.0)

    # 4. Recency bonus
    if paper.year:
        try:
            year_int = int(str(paper.year)[:4])
            diff = max(0, current_year - year_int)
            if diff == 0 or diff == 1:
                score += 15.0
            elif diff <= 3:
                score += 10.0
            elif diff <= 5:
                score += 6.0
            elif diff <= 10:
                score += 3.0
        except ValueError:
            pass

    # 5. Full PDF access bonus
    if paper.pdf_url:
        score += 10.0

    return round(score, 2)


def rank_papers(papers: List[Paper], query: str, limit: int = 30) -> List[Paper]:
    """
    Score, sort, and return top `limit` papers deterministically.
    Ties are broken stably by title alphabetically and year descending.
    """
    for paper in papers:
        paper.score = compute_paper_score(paper, query)

    # Sort descending by score, tie-break by year descending then title
    sorted_papers = sorted(
        papers,
        key=lambda p: (
            p.score or 0.0,
            int(str(p.year)[:4]) if (p.year and str(p.year)[:4].isdigit()) else 0,
            p.title.lower()
        ),
        reverse=True
    )

    return sorted_papers[:limit]
