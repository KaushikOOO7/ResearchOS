"""Research endpoints: multi-source search and paper lookup."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.helpers import build_research_response
from app.research.search_engine import run_search
from app.schemas.research import PaperDetailResponse, ResearchRequest, ResearchResponse
from app.services.cache import search_cache
from app.services.paper_store import get_paper, remember_papers
from app.utils.logging_setup import get_logger

logger = get_logger("research-api")

router = APIRouter(tags=["research"])


@router.post("/research", response_model=ResearchResponse)
def research(request: ResearchRequest) -> ResearchResponse:
    """
    Run the full retrieval + ranking pipeline and return the top papers.

    1. understand the query, 2. query every applicable provider in parallel,
    3. normalise + deduplicate the candidate pool, 4. score relevance / quality
    / recency / citation impact / source reliability, 5. rank, 6. return the
    best N (default 30).
    """
    cache_key = search_cache.make_key(
        "research",
        request.query.lower(),
        request.limit,
        sorted(request.sources or []),
        request.year_from,
        request.open_access_only,
    )
    cached = search_cache.get(cache_key)
    if cached is not None:
        logger.info("Search served from cache")
        return cached

    outcome = run_search(
        query=request.query,
        limit=request.limit,
        source_names=request.sources,
        year_from=request.year_from,
        open_access_only=request.open_access_only,
    )

    response = build_research_response(outcome, request.query)
    remember_papers(outcome.papers)

    # Only cache successful retrievals; empty results should be retried.
    if outcome.papers:
        search_cache.set(cache_key, response)

    return response


@router.get("/papers/{paper_id}", response_model=PaperDetailResponse)
def paper_detail(paper_id: str) -> PaperDetailResponse:
    """Return a paper that was returned by a recent search."""
    paper = get_paper(paper_id)
    if not paper:
        raise HTTPException(
            status_code=404,
            detail="This paper is not in the current session. Run the search again to load it.",
        )
    return PaperDetailResponse(paper=paper)
