"""End-to-end pipeline tests with fake providers (no network)."""

from __future__ import annotations

from typing import List

from app.models.paper import Paper, QueryAnalysis
from app.research.base import ResearchSource, build_paper
from app.research.search_engine import run_search
from app.services.cache import TTLCache


class FakeSource(ResearchSource):
    """Provider stub returning a fixed list or raising a fixed error."""

    def __init__(self, name: str, papers: List[Paper] | None = None, error: str | None = None):
        self.name = name
        self._papers = papers or []
        self._error = error

    def fetch(self, query: str, limit: int, query_analysis: QueryAnalysis) -> List[Paper]:
        if self._error:
            raise RuntimeError(self._error)
        return self._papers[:limit]


def _paper(title: str, **kwargs) -> Paper:
    return build_paper(title=title, source=kwargs.pop("source", "Fake"), **kwargs)


def test_pipeline_collects_dedupes_and_ranks():
    shared_doi = "10.1000/shared"
    source_a = FakeSource(
        "SourceA",
        [
            _paper(
                "Graph Neural Networks for Molecular Property Prediction",
                source="SourceA",
                doi=shared_doi,
                year=2024,
                abstract="graph neural networks for molecular property prediction on MoleculeNet",
                citation_count=50,
            ),
            _paper("Unrelated Power Grid Paper", source="SourceA", year=2019),
        ],
    )
    source_b = FakeSource(
        "SourceB",
        [
            _paper(
                "Graph Neural Networks for Molecular Property Prediction",
                source="SourceB",
                doi="https://doi.org/10.1000/SHARED",
                year=2024,
                abstract="graph neural networks for molecular property prediction",
                citation_count=52,
            ),
            _paper("Another Molecular Paper", source="SourceB", year=2023),
        ],
    )

    outcome = run_search(
        "Graph neural networks for molecular property prediction",
        limit=30,
        sources=[source_a, source_b],
    )

    assert outcome.stats.candidates_collected == 4
    assert outcome.stats.duplicates_removed == 1
    assert len(outcome.papers) == 3
    # The duplicate kept the highest citation count and both sources.
    merged = next(p for p in outcome.papers if p.doi == shared_doi)
    assert merged.citation_count == 52
    assert set(merged.sources) == {"SourceA", "SourceB"}
    # The most relevant paper is ranked first.
    assert outcome.papers[0].id == merged.id
    assert outcome.papers[0].rank == 1
    assert all(p.overall_score >= 0 for p in outcome.papers)


def test_provider_failure_does_not_fail_the_search():
    good = FakeSource("Good", [_paper("Graph Neural Networks for Drug Discovery",
                                      abstract="graph neural networks for drug discovery",
                                      year=2024)])
    broken = FakeSource("Broken", error="connection reset")

    outcome = run_search("graph neural networks for drug discovery", sources=[good, broken])

    assert len(outcome.papers) == 1
    statuses = {status.name: status for status in outcome.source_outcomes}
    assert statuses["Broken"].ok is False
    assert "connection reset" in statuses["Broken"].error
    assert statuses["Good"].result_count == 1


def test_empty_results_produce_actionable_message():
    broken = FakeSource("Broken", error="timeout")
    outcome = run_search("quantum teleportation of coffee", sources=[broken])

    assert outcome.papers == []
    assert outcome.message
    assert "Broken" in outcome.message

    failed = run_search("quantum teleportation of coffee", sources=[FakeSource("Empty", [])])
    assert failed.papers == []
    assert "No papers were found" in failed.message


def test_limit_and_filters_are_applied():
    papers = [
        _paper(f"Graph Neural Network Study {index}", year=2015 + index, pdf_url=None)
        for index in range(6)
    ]
    papers.append(_paper("Graph Neural Network With PDF", year=2024, pdf_url="https://example.org/a.pdf"))

    outcome = run_search("graph neural network", limit=3, sources=[FakeSource("S", papers)])
    assert len(outcome.papers) == 3

    filtered = run_search(
        "graph neural network", year_from=2023, sources=[FakeSource("S", papers)]
    )
    assert all(paper.year and paper.year >= 2023 for paper in filtered.papers)

    oa_only = run_search(
        "graph neural network", open_access_only=True, limit=10,
        sources=[FakeSource("S", papers)],
    )
    assert all(paper.pdf_url for paper in oa_only.papers)


def test_query_understanding_is_reported():
    outcome = run_search("Recent GNN methods for drug discovery", sources=[FakeSource("S", [])])
    analysis = outcome.query_analysis
    assert analysis.acronyms.get("gnn") == "graph neural network"
    assert analysis.is_biomedical is True
    assert analysis.wants_recent is True
    assert any("PubMed" in note for note in outcome.notes)


def test_ttl_cache_expires_entries():
    cache = TTLCache(max_entries=2, ttl_seconds=60)
    key = cache.make_key("q", 1)
    cache.set(key, {"ok": True})
    assert cache.get(key) == {"ok": True}
    assert cache.get(cache.make_key("missing")) is None

    short = TTLCache(max_entries=2, ttl_seconds=0)
    short.set("k", 1)
    assert short.get("k") is None

    bounded = TTLCache(max_entries=1, ttl_seconds=60)
    bounded.set("a", 1)
    bounded.set("b", 2)
    assert bounded.get("a") is None
    assert bounded.get("b") == 2
