"""
Tests for academic research pipeline: normalization, deduplication, ranking, and search engine.
"""

from unittest.mock import patch
from app.schemas.paper import Paper
from app.research.normalizer import normalize_title, clean_doi, clean_arxiv_id, build_paper_id
from app.research.deduplicator import deduplicate_papers
from app.research.ranker import compute_paper_score, rank_papers
from app.research.engine import execute_multi_provider_search


def test_normalization():
    """Test normalization of titles, DOIs, and arXiv IDs."""
    raw_title = "   Deep  Residual Learning for   Image Recognition.\n\n"
    assert normalize_title(raw_title) == "Deep Residual Learning for Image Recognition."

    assert clean_doi("https://doi.org/10.1145/1234567") == "10.1145/1234567"
    assert clean_doi("doi: 10.1038/nature12345") == "10.1038/nature12345"
    assert clean_doi(None) is None

    assert clean_arxiv_id("https://arxiv.org/abs/2301.00001v2") == "2301.00001"
    assert clean_arxiv_id("2301.00001.pdf") == "2301.00001"
    assert build_paper_id("arXiv", "2301.00001") == "arxiv:2301.00001"


def test_deduplication():
    """Test duplicate paper removal and metadata merging."""
    paper1 = Paper(
        id="arxiv:1",
        title="Attention Is All You Need",
        authors=["Vaswani"],
        abstract="Short abstract",
        year="2017",
        doi=None,
        arxiv_id="1706.03762",
        paper_url="https://arxiv.org/abs/1706.03762",
        pdf_url="https://arxiv.org/pdf/1706.03762",
        source="arXiv",
        citation_count=None,
    )
    # Duplicate with same arXiv ID but richer citations and longer abstract from Semantic Scholar
    paper2 = Paper(
        id="s2:1",
        title="Attention Is All You Need",
        authors=["Vaswani", "Shazeer", "Parmar"],
        abstract="Longer complete abstract explaining the transformer architecture.",
        year="2017",
        doi="10.5555/3295222.3295349",
        arxiv_id="1706.03762",
        paper_url="https://www.semanticscholar.org/paper/1",
        pdf_url=None,
        source="Semantic Scholar",
        citation_count=120000,
    )
    # Different paper
    paper3 = Paper(
        id="arxiv:2",
        title="BERT: Pre-training of Deep Bidirectional Transformers",
        authors=["Devlin"],
        abstract="BERT language representation model.",
        year="2018",
        doi=None,
        arxiv_id="1810.04805",
        paper_url="https://arxiv.org/abs/1810.04805",
        source="arXiv",
    )

    deduped = deduplicate_papers([paper1, paper2, paper3])
    assert len(deduped) == 2
    # Verify paper1 got merged with paper2's metadata
    first = deduped[0]
    assert first.citation_count == 120000
    assert first.doi == "10.5555/3295222.3295349"
    assert "transformer" in first.abstract


def test_ranking_order():
    """Test relevance scoring and deterministic ranking order."""
    query = "quantum computing error correction"

    paper_low = Paper(
        id="1",
        title="General Review of Computing Algorithms",
        abstract="Covers classical algorithms and basic sorting.",
        year="2015",
    )
    paper_high = Paper(
        id="2",
        title="Quantum Computing Error Correction via Surface Codes",
        abstract="We demonstrate quantum computing error correction with low overhead.",
        year="2025",
        citation_count=150,
        pdf_url="https://example.com/quantum.pdf",
    )

    ranked = rank_papers([paper_low, paper_high], query=query)
    assert len(ranked) == 2
    assert ranked[0].id == "2"
    assert (ranked[0].score or 0) > (ranked[1].score or 0)


def test_search_when_one_provider_fails():
    """Test that search succeeds even if one academic provider raises an exception."""
    mock_arxiv_papers = [
        Paper(id="arxiv:1", title="ArXiv Paper On Transformers", year="2024")
    ]

    with patch("app.research.engine.search_arxiv", return_value=mock_arxiv_papers), \
         patch("app.research.engine.search_openalex", side_effect=Exception("OpenAlex timeout")), \
         patch("app.research.engine.search_crossref", return_value=[]), \
         patch("app.research.engine.search_semantic_scholar", return_value=[]), \
         patch("app.research.engine.search_pubmed", return_value=[]):

        papers, queried, succeeded = execute_multi_provider_search("transformers", target_count=30)
        assert len(papers) == 1
        assert "arXiv" in succeeded
        assert "OpenAlex" not in succeeded
        assert "arXiv" in queried


def test_search_when_all_providers_fail():
    """Test behavior when all academic providers fail or return zero results."""
    with patch("app.research.engine.search_arxiv", side_effect=Exception("Timeout")), \
         patch("app.research.engine.search_openalex", side_effect=Exception("Timeout")), \
         patch("app.research.engine.search_crossref", side_effect=Exception("Timeout")), \
         patch("app.research.engine.search_semantic_scholar", side_effect=Exception("Timeout")), \
         patch("app.research.engine.search_pubmed", side_effect=Exception("Timeout")):

        papers, queried, succeeded = execute_multi_provider_search("transformers", target_count=30)
        assert len(papers) == 0
        assert len(succeeded) == 0
        assert len(queried) == 5
