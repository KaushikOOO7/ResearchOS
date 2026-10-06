"""
ResearchOS multi-source search engine.

Pipeline (see project brief, section 8):

    USER QUERY
      -> QUERY UNDERSTANDING
      -> MULTI-SOURCE SEARCH (parallel, per-provider isolation)
      -> COLLECT CANDIDATES (~50-100)
      -> NORMALISE METADATA
      -> DEDUPLICATE
      -> RELEVANCE / QUALITY / RECENCY / CITATION / SOURCE SCORING
      -> FINAL RANKING
      -> TOP N PAPERS

No single provider can fail the request: every source is wrapped, timed and
reported in ``SourceStatus`` so the UI can explain exactly what happened.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from app.config import RankingWeights, settings
from app.models.paper import Paper, QueryAnalysis, SearchStats, SourceStatus
from app.research.arxiv import ArxivSource
from app.research.base import ResearchSource, SourceOutcome
from app.research.crossref import CrossrefSource
from app.research.deduplicator import deduplicate
from app.research.openalex import OpenAlexSource
from app.research.pubmed import PubMedSource
from app.research.query_understanding import analyze_query
from app.research.ranker import rank_papers, weighting_notes
from app.research.semantic_scholar import SemanticScholarSource
from app.utils.logging_setup import get_logger

logger = get_logger("search")

#: Relative retrieval budget per provider (higher = more candidates).
_BUDGET_WEIGHTS: Dict[str, float] = {
    "OpenAlex": 1.30,
    "Crossref": 1.15,
    "arXiv": 1.25,
    "Semantic Scholar": 0.85,
    "PubMed": 0.70,
}

_MIN_PER_SOURCE = 10
_MAX_PER_SOURCE = 100


def default_sources() -> List[ResearchSource]:
    """All registered providers, in a stable order."""
    return [
        OpenAlexSource(),
        ArxivSource(),
        CrossrefSource(),
        SemanticScholarSource(),
        PubMedSource(),
    ]


def _allocate_budgets(sources: Sequence[ResearchSource], target: int) -> Dict[str, int]:
    """Split the candidate target across providers proportionally."""
    weights = {source.name: _BUDGET_WEIGHTS.get(source.name, 0.8) for source in sources}
    total = sum(weights.values()) or 1.0
    budgets: Dict[str, int] = {}
    for source in sources:
        share = target * weights[source.name] / total
        budgets[source.name] = int(max(_MIN_PER_SOURCE, min(round(share), _MAX_PER_SOURCE)))
    return budgets


@dataclass
class SearchOutcome:
    """Everything the API layer needs to build the response."""

    query_analysis: QueryAnalysis
    papers: List[Paper]
    source_outcomes: List[SourceOutcome] = field(default_factory=list)
    stats: SearchStats = field(default_factory=SearchStats)
    weights: RankingWeights = field(default_factory=RankingWeights)
    notes: List[str] = field(default_factory=list)
    message: Optional[str] = None


def _outcome_to_status(outcome: SourceOutcome) -> SourceStatus:
    return SourceStatus(
        name=outcome.name,
        ok=outcome.ok,
        result_count=outcome.result_count,
        elapsed_ms=outcome.elapsed_ms,
        error=outcome.error,
        configured=outcome.configured,
    )


def _no_results_message(outcomes: Sequence[SourceOutcome]) -> str:
    """Build an honest, actionable message when nothing was retrieved."""
    failed = [outcome for outcome in outcomes if not outcome.ok]
    skipped = [outcome for outcome in outcomes if outcome.ok and outcome.error == "not configured"]
    succeeded = [outcome for outcome in outcomes if outcome.ok and outcome.result_count > 0]

    if succeeded:
        return "No paper matched the query filters. Try broadening the query or removing filters."
    if failed and not skipped:
        names = ", ".join(outcome.name for outcome in failed)
        return (
            f"No academic source could be reached ({names}). "
            "This is usually a temporary network or provider issue — please try again."
        )
    if failed:
        names = ", ".join(outcome.name for outcome in failed)
        return f"Providers unavailable: {names}. No papers were retrieved for this query."
    return "No papers were found for this query. Try rephrasing your research idea."


def run_search(
    query: str,
    limit: Optional[int] = None,
    source_names: Optional[Sequence[str]] = None,
    year_from: Optional[int] = None,
    open_access_only: bool = False,
    sources: Optional[Sequence[ResearchSource]] = None,
) -> SearchOutcome:
    """
    Execute the full retrieval + ranking pipeline.

    Returns a :class:`SearchOutcome`; never raises for provider failures.
    """
    started = time.perf_counter()
    logger.info("Search started")
    logger.info("Query: %s", query)

    query_analysis = analyze_query(query)
    if query_analysis.notes:
        for note in query_analysis.notes:
            logger.info("Query understanding: %s", note)

    available = list(sources) if sources is not None else default_sources()

    if source_names:
        wanted = {name.strip().lower() for name in source_names if name and name.strip()}
        available = [source for source in available if source.name.lower() in wanted]
        unknown = wanted - {source.name.lower() for source in available}
        if unknown:
            logger.info("Ignoring unknown sources: %s", ", ".join(sorted(unknown)))

    usable = [
        source
        for source in available
        if source.is_configured() and source.is_applicable(query_analysis)
    ]
    skipped = [source for source in available if source not in usable]
    for source in skipped:
        if not source.is_configured():
            logger.info("%s skipped: not configured", source.name)
        else:
            logger.info("%s skipped: not applicable to this query", source.name)

    target = limit or settings.max_results
    budgets = _allocate_budgets(usable, settings.target_candidates)

    outcomes: List[SourceOutcome] = []
    candidates: List[Paper] = []

    if usable:
        workers = min(len(usable), 5)
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="researchos-src") as pool:
            futures = {
                pool.submit(source.search, query, budgets[source.name], query_analysis): source
                for source in usable
            }
            try:
                for future in as_completed(
                    futures, timeout=settings.search_deadline_seconds
                ):
                    source = futures[future]
                    try:
                        outcome = future.result()
                    except Exception as exc:  # noqa: BLE001 - defensive
                        outcome = SourceOutcome(
                            name=source.name, ok=False, error=f"{type(exc).__name__}: {exc}"
                        )
                    outcomes.append(outcome)
                    candidates.extend(outcome.papers)
            except TimeoutError:
                logger.info(
                    "Search deadline (%.0fs) reached — continuing with partial results",
                    settings.search_deadline_seconds,
                )
                for future, source in futures.items():
                    if future.done():
                        continue
                    outcomes.append(
                        SourceOutcome(
                            name=source.name,
                            ok=False,
                            error=f"timed out after {settings.search_deadline_seconds:.0f}s",
                        )
                    )
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
    else:
        logger.info("No applicable providers for this query")

    outcomes.sort(key=lambda outcome: outcome.name)
    for outcome in outcomes:
        if outcome.ok:
            logger.info("%s results: %d (%d ms)", outcome.name, outcome.result_count, outcome.elapsed_ms)
        else:
            logger.info("%s failed: %s", outcome.name, outcome.error)

    for source in skipped:
        outcomes.append(
            SourceOutcome(
                name=source.name,
                ok=True,
                configured=source.is_configured(),
                error="not configured" if not source.is_configured() else "not applicable to this query",
            )
        )
    outcomes.sort(key=lambda outcome: outcome.name)

    logger.info("Candidates collected: %d", len(candidates))

    # --- Filters -----------------------------------------------------------
    effective_year_from = year_from or query_analysis.year_from
    filtered: List[Paper] = []
    for paper in candidates:
        if not paper.title:
            continue
        if effective_year_from and paper.year and paper.year < effective_year_from:
            continue
        if open_access_only and not paper.pdf_url:
            continue
        filtered.append(paper)

    unique, removed = deduplicate(filtered)
    logger.info("Candidates after dedup: %d", len(unique))

    ranked = rank_papers(unique, query_analysis, settings.weights)
    top = ranked[: max(1, min(target, settings.max_results))] if ranked else []
    logger.info("Final Top %d generated", len(top))

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    stats = SearchStats(
        candidates_collected=len(candidates),
        duplicates_removed=removed,
        returned=len(top),
        providers_queried=len(outcomes),
        providers_succeeded=sum(1 for outcome in outcomes if outcome.ok and outcome.result_count),
        elapsed_ms=elapsed_ms,
    )

    return SearchOutcome(
        query_analysis=query_analysis,
        papers=top,
        source_outcomes=outcomes,
        stats=stats,
        weights=settings.weights,
        notes=query_analysis.notes + weighting_notes(settings.weights),
        message=None if top else _no_results_message(outcomes),
    )
