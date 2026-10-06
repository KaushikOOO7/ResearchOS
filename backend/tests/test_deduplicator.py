"""Deduplication and metadata-merging tests."""

from __future__ import annotations

from app.models.paper import Paper
from app.research.deduplicator import deduplicate, merge_papers
from app.research.base import build_paper


def _paper(**kwargs) -> Paper:
    return build_paper(**kwargs)


def test_same_doi_is_merged():
    a = _paper(title="Graph Neural Networks for Drug Discovery", source="arXiv",
               doi="10.1000/x", year=2024, abstract="short")
    b = _paper(title="Graph Neural Networks for Drug Discovery", source="OpenAlex",
               doi="https://doi.org/10.1000/X", year=2024, abstract="a much longer abstract " * 5,
               citation_count=42)

    unique, removed = deduplicate([a, b])
    assert removed == 1
    assert len(unique) == 1
    merged = unique[0]
    assert set(merged.sources) == {"arXiv", "OpenAlex"}
    assert merged.citation_count == 42
    assert len(merged.abstract) > 50


def test_same_arxiv_id_is_merged_even_with_different_titles():
    a = _paper(title="A Survey of Graph Neural Networks", source="arXiv", arxiv_id="2401.00001v1")
    b = _paper(title="A Survey of Graph Neural Networks ", source="Semantic Scholar",
               arxiv_id="2401.00001")
    unique, removed = deduplicate([a, b])
    assert removed == 1
    assert len(unique) == 1


def test_fuzzy_title_match_merges_when_years_agree():
    a = _paper(title="Graph Neural Networks for Molecular Property Prediction",
               source="Crossref", year=2023)
    b = _paper(title="Graph Neural Networks for Molecular Property Prediction: A Survey",
               source="OpenAlex", year=2024)
    unique, removed = deduplicate([a, b])
    assert removed == 1


def test_unrelated_titles_are_not_merged():
    a = _paper(title="Graph Neural Networks for Drug Discovery", source="arXiv", year=2024)
    b = _paper(title="Power Grid Load Forecasting with Recurrent Networks",
               source="OpenAlex", year=2019)
    unique, removed = deduplicate([a, b])
    assert removed == 0
    assert len(unique) == 2


def test_merge_prefers_richest_metadata():
    arxiv = _paper(
        title="Federated Learning for IoT",
        source="arXiv",
        doi=None,
        year=2022,
        pdf_url="https://arxiv.org/pdf/2201.00001",
        venue="arXiv (preprint)",
        authors=["Ada Lovelace"],
    )
    openalex = _paper(
        title="Federated Learning for IoT",
        source="OpenAlex",
        doi="10.1000/fl",
        year=2022,
        citation_count=17,
        venue="IEEE Internet of Things Journal",
        authors=["Ada Lovelace", "Alan Turing", "Grace Hopper"],
        keywords=["federated learning"],
    )
    merged = merge_papers([arxiv, openalex])
    assert merged.doi == "10.1000/fl"
    assert merged.venue == "IEEE Internet of Things Journal"
    assert merged.citation_count == 17
    assert len(merged.authors) == 3
    # The arXiv PDF link is preserved even though OpenAlex won the metadata.
    assert merged.pdf_url == "https://arxiv.org/pdf/2201.00001"


def test_deduplicate_is_deterministic():
    papers = [
        _paper(title="Same Title Here", source="arXiv", year=2021),
        _paper(title="Same Title Here", source="Crossref", year=2021),
        _paper(title="Totally Different Paper About Cats", source="arXiv", year=2021),
    ]
    first, _ = deduplicate(papers)
    second, _ = deduplicate(papers)
    assert [p.title for p in first] == [p.title for p in second]
    assert len(first) == 2
