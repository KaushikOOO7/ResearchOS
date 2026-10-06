"""Ranking engine tests: relevance ordering, honest scoring, explainability."""

from __future__ import annotations

import pytest

from app.config import RankingWeights
from app.research.base import build_paper
from app.research.query_understanding import analyze_query
from app.research.ranking import (
    combine_overall,
    compute_citation,
    compute_quality,
    compute_recency,
    rank_papers,
)
from app.research.ranking import weighting_notes

WEIGHTS = RankingWeights()


def _rank(query: str, papers: list):
    return rank_papers(papers, analyze_query(query), WEIGHTS)


def test_relevant_paper_outranks_keyword_dropping_paper():
    query = "Graph neural networks for molecular property prediction"
    relevant = build_paper(
        title="Graph Neural Networks for Molecular Property Prediction",
        abstract=("We propose a message passing graph neural network for molecular "
                  "property prediction on MoleculeNet benchmarks."),
        source="OpenAlex",
        year=2024,
        doi="10.1/a",
        citation_count=120,
        doc_type="journal-article",
        venue="Journal of Cheminformatics",
    )
    unrelated = build_paper(
        title="Neural Networks for Power Grid Optimization",
        abstract="We optimise power grid scheduling using neural networks.",
        source="OpenAlex",
        year=2024,
        doi="10.1/b",
        citation_count=400,
        doc_type="journal-article",
        venue="Energy Systems",
    )

    ranked = _rank(query, [unrelated, relevant])
    assert [paper.rank for paper in ranked] == [1, 2]
    assert ranked[0].title.startswith("Graph Neural Networks")
    assert ranked[0].relevance_score > ranked[1].relevance_score * 2


def test_single_keyword_hit_does_not_float_unrelated_paper():
    query = "Graph neural networks for molecular property prediction"
    related = build_paper(
        title="Molecular Property Prediction with Graph Neural Networks",
        abstract="Graph neural networks for molecular property prediction.",
        source="arXiv",
        year=2023,
    )
    keyword_bait = build_paper(
        title="A Neural Network Approach to Traffic Prediction",
        abstract="Neural networks are used for traffic prediction in smart cities.",
        source="arXiv",
        year=2023,
    )

    ranked = _rank(query, [keyword_bait, related])
    assert ranked[0].title.startswith("Molecular Property Prediction")


def test_scores_are_bounded_and_explained():
    query = "federated learning for medical imaging"
    papers = [
        build_paper(
            title="Federated Learning for Medical Imaging",
            abstract="Federated learning for medical imaging across hospitals.",
            source="PubMed",
            year=2022,
            doi="10.1/c",
            citation_count=30,
            doc_type="journal-article",
            venue="Medical Image Analysis",
        )
    ]
    ranked = _rank(query, papers)
    paper = ranked[0]

    for value in (
        paper.relevance_score,
        paper.quality_score,
        paper.source_score,
        paper.overall_score,
    ):
        assert 0.0 <= value <= 100.0
    assert paper.citation_score is not None
    assert set(paper.score_explanations) >= {
        "relevance", "quality", "recency", "citation", "source", "overall",
    }
    assert paper.matched_terms


def test_missing_citation_count_is_not_scored_as_zero():
    paper = build_paper(title="Untracked Preprint on Graph Learning", source="arXiv", year=2024)
    score, reason = compute_citation(paper)
    assert score is None
    assert "not available" in reason

    overall, effective = combine_overall(
        {"relevance": 80.0, "quality": 50.0, "citation": None, "recency": 100.0, "source": 82.0},
        WEIGHTS,
    )
    # Citation weight is redistributed instead of counted as a zero.
    assert "citation" not in effective
    assert pytest.approx(sum(effective.values()), rel=1e-6) == 1.0
    assert overall > 70


def test_recency_and_quality_are_metadata_based():
    old = build_paper(title="Old Paper", source="Crossref", year=2001, doi="10.1/old")
    fresh = build_paper(title="Fresh Paper", source="Crossref", year=2026, doi="10.1/new")
    old_recency, _ = compute_recency(old, current_year=2026)
    fresh_recency, _ = compute_recency(fresh, current_year=2026)
    assert fresh_recency == 100
    assert old_recency < 20

    unknown_year = build_paper(title="No Year", source="Crossref")
    assert compute_recency(unknown_year)[0] is None

    rich = build_paper(
        title="Rich Metadata Paper",
        abstract="x" * 900,
        source="OpenAlex",
        year=2024,
        doi="10.1/rich",
        venue="Nature",
        doc_type="journal-article",
        authors=["A", "B", "C"],
        keywords=["kw"],
    )
    rich.sources = ["OpenAlex", "Crossref", "arXiv"]
    sparse = build_paper(title="Sparse", source="arXiv")
    assert compute_quality(rich)[0] > compute_quality(sparse)[0]


def test_source_reliability_uses_best_indexing_source():
    paper = build_paper(title="Multi-source Paper", source="arXiv", year=2024)
    paper.sources = ["arXiv", "OpenAlex"]
    ranked = _rank("multi source paper", [paper])
    assert ranked[0].source_score == 92.0


def test_ranking_is_stable_for_equal_scores():
    papers = [
        build_paper(title="Alpha Study on Graph Networks", source="arXiv", year=2020),
        build_paper(title="Beta Study on Graph Networks", source="arXiv", year=2020),
    ]
    first = [p.title for p in _rank("graph networks", papers)]
    second = [p.title for p in _rank("graph networks", list(reversed(papers)))]
    assert first == second


def test_weighting_notes_document_the_formula():
    notes = "\n".join(weighting_notes(WEIGHTS))
    assert "0.50×relevance" in notes
    assert "renormalised" in notes
