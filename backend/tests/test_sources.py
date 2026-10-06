"""Provider parsing tests (offline, using realistic payload fixtures)."""

from __future__ import annotations

from app.research import arxiv as arxiv_module
from app.research import crossref as crossref_module
from app.research import openalex as openalex_module
from app.research import pubmed as pubmed_module
from app.research.arxiv import ArxivSource
from app.research.crossref import CrossrefSource
from app.research.openalex import OpenAlexSource, reconstruct_abstract
from app.research.pubmed import PubMedSource
from app.research.query_understanding import analyze_query
from app.research.semantic_scholar import SemanticScholarSource


class TestArxiv:
    def test_parses_entries(self, monkeypatch, arxiv_xml):
        monkeypatch.setattr(arxiv_module, "get_text", lambda *a, **k: arxiv_xml)
        papers = ArxivSource().fetch("graph neural networks", 10, analyze_query("graph neural networks"))

        assert len(papers) == 2
        first = papers[0]
        assert first.source == "arXiv"
        assert first.arxiv_id == "2401.01234"
        assert first.year == 2024
        assert first.doi == "10.1000/example.doi"
        assert first.pdf_url.endswith("2401.01234v2")
        assert first.authors == ["Ada Lovelace", "Alan Turing"]
        assert "message passing" in first.abstract
        # Title whitespace from the XML is collapsed.
        assert "\n" not in first.title

    def test_provider_failure_is_isolated(self, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("arXiv is down")

        monkeypatch.setattr(arxiv_module, "get_text", boom)
        outcome = ArxivSource().search("graph networks", 5, analyze_query("graph networks"))
        assert outcome.ok is False
        assert outcome.papers == []
        assert "arXiv is down" in outcome.error


class TestOpenAlex:
    def test_reconstruct_abstract_orders_words(self):
        inverted = {"world": [1], "hello": [0]}
        assert reconstruct_abstract(inverted) == "hello world"
        assert reconstruct_abstract(None) == ""

    def test_parses_works(self, monkeypatch, openalex_payload):
        monkeypatch.setattr(openalex_module, "get_json", lambda *a, **k: openalex_payload)
        papers = OpenAlexSource().fetch("graph neural networks", 10, analyze_query("graph neural networks"))

        assert len(papers) == 2
        first = papers[0]
        assert first.doi == "10.1000/example.doi"
        assert first.citation_count == 87
        assert first.venue == "Journal of Cheminformatics"
        assert first.pdf_url == "https://example.org/paper.pdf"
        assert first.abstract.startswith("Graph neural networks for molecular")
        assert first.is_open_access is True
        assert "molecular property prediction" in first.keywords


class TestCrossref:
    def test_parses_items_and_skips_non_papers(self, monkeypatch, crossref_payload):
        monkeypatch.setattr(crossref_module, "get_json", lambda *a, **k: crossref_payload)
        papers = CrossrefSource().fetch("graph neural networks", 10, analyze_query("graph neural networks"))

        assert len(papers) == 1  # the "component" record is excluded
        paper = papers[0]
        assert paper.year == 2024
        assert paper.authors == ["Ada Lovelace", "Alan Turing"]
        assert paper.citation_count == 91
        assert paper.pdf_url == "https://example.org/crossref.pdf"
        # JATS markup is stripped from the abstract.
        assert "<jats" not in paper.abstract


class TestSemanticScholar:
    def test_is_skipped_without_an_api_key(self, monkeypatch):
        from app.research import semantic_scholar as s2_module

        # Settings are frozen; simulate "no key" through the module reference
        # the provider reads at call time.
        class NoKey:
            semantic_scholar_api_key = ""

        monkeypatch.setattr(s2_module, "settings", NoKey())
        source = SemanticScholarSource()
        assert source.is_configured() is False

        outcome = source.search("graph networks", 5, analyze_query("graph networks"))
        assert outcome.ok is True
        assert outcome.result_count == 0
        assert outcome.configured is False
        # A skipped provider reports a clear reason instead of failing.
        assert outcome.error == "not configured"


class TestPubMed:
    def test_requires_biomedical_signal(self):
        source = PubMedSource()
        assert source.is_applicable(analyze_query("graph neural networks for drug discovery"))
        assert not source.is_applicable(analyze_query("load balancing in distributed databases"))

    def test_parses_articles(self, monkeypatch, pubmed_xml):
        monkeypatch.setattr(pubmed_module, "get_json", lambda *a, **k: {"esearchresult": {"idlist": ["12345678"]}})
        monkeypatch.setattr(pubmed_module, "get_text", lambda *a, **k: pubmed_xml)

        papers = PubMedSource().fetch(
            "graph neural networks for drug discovery", 5,
            analyze_query("graph neural networks for drug discovery"),
        )
        assert len(papers) == 1
        paper = papers[0]
        assert paper.doi == "10.1000/pubmed.doi"
        assert paper.year == 2023
        assert paper.authors == ["Lovelace A"]
        assert "BACKGROUND" in paper.abstract
        assert paper.paper_url.endswith("/12345678/")
        # PubMed results are not claimed to have a downloadable PDF.
        assert paper.pdf_url is None
