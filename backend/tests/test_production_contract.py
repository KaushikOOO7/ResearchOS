"""
Production contract tests.

Covers the deployment-facing requirements: path aliases (/api/*), the search
response fields the frontend depends on, normalisation of dates/journals, and
the exact behaviour when Gemini is not configured.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.paper import QueryAnalysis, SearchStats, SourceStatus
from app.research.base import build_paper
from app.research.normalizer import build_paper as normalizer_build_paper
from app.research.normalizer import normalize_date, normalize_year
from app.research.search_engine import SearchOutcome
from app.services.cache import search_cache


@pytest.fixture
def client() -> TestClient:
    search_cache.clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    search_cache.clear()


@pytest.fixture
def stub_search(monkeypatch):
    """Two ranked papers plus mixed provider outcomes."""
    papers = [
        build_paper(
            title="Graph Neural Networks for Molecular Property Prediction",
            abstract="graph neural networks for molecular property prediction",
            source="OpenAlex",
            year=2024,
            published_date="2024-03-01",
            doi="10.1000/a",
            citation_count=120,
            doc_type="journal-article",
            venue="Journal of Cheminformatics",
            journal="Journal of Cheminformatics",
            pdf_url="https://example.org/a.pdf",
        ),
        build_paper(
            title="Power Grid Forecasting with Neural Networks",
            abstract="neural networks for power grid forecasting",
            source="Crossref",
            year=2019,
            doi="10.1000/b",
            doc_type="journal-article",
        ),
    ]
    from app.config import RankingWeights
    from app.research.query_understanding import analyze_query
    from app.research.ranking import rank_papers

    analysis = analyze_query("graph neural networks for molecular property prediction")
    ranked = rank_papers(papers, analysis, RankingWeights())

    import app.api.research as research_api

    monkeypatch.setattr(
        research_api,
        "run_search",
        lambda query, **kwargs: SearchOutcome(
            query_analysis=analysis,
            papers=ranked,
            source_outcomes=[
                SourceStatus(name="OpenAlex", ok=True, result_count=42, elapsed_ms=900),
                SourceStatus(name="arXiv", ok=True, result_count=0, elapsed_ms=800),
                SourceStatus(
                    name="Crossref", ok=False, error="ProviderError: network error", elapsed_ms=120
                ),
                SourceStatus(name="PubMed", ok=True, error="not applicable to this query"),
                SourceStatus(name="Semantic Scholar", ok=True, configured=False, error="not configured"),
            ],
            stats=SearchStats(candidates_collected=60, duplicates_removed=6, returned=len(ranked)),
            notes=["test note"],
        ),
    )


class TestPathAliases:
    """Every documented route must work at both path styles."""

    @pytest.mark.parametrize("path", ["/", "/api"])
    def test_root(self, client, path):
        payload = client.get(path).json()
        assert payload["service"] == "ResearchOS API"
        assert payload["status"] == "healthy"
        assert payload["version"]

    @pytest.mark.parametrize(
        "path", ["/health", "/api/health"]
    )
    def test_health_needs_no_gemini(self, client, path):
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "healthy"
        assert payload["service"] == "ResearchOS"
        assert isinstance(payload["gemini_configured"], bool)
        assert payload["network"]["internet"] in {True, False}

    def test_swagger_and_openapi_available(self, client):
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json").json()
        for route in ("/research", "/analyze-paper", "/health", "/api/health"):
            assert route in schema["paths"], route

    @pytest.mark.parametrize("path", ["/research", "/api/research"])
    def test_research_available_on_both_paths(self, client, stub_search, path):
        response = client.post(
            path, json={"query": "graph neural networks for molecular property prediction"}
        )
        assert response.status_code == 200
        assert response.json()["count"] == 2


class TestSearchResponseContract:
    def test_response_fields_used_by_the_frontend(self, client, stub_search):
        body = client.post(
            "/research", json={"query": "graph neural networks for molecular property prediction"}
        ).json()

        assert body["status"] == "success"
        assert body["query"]
        assert body["count"] == len(body["papers"]) == 2

        # Provider outcome map (section 33 of the spec).
        assert body["providers"] == {
            "openalex": "success",
            "arxiv": "empty",
            "crossref": "failed",
            "pubmed": "skipped",
            "semantic_scholar": "skipped",
        }
        # Rich per-provider telemetry is still available.
        assert {s["name"] for s in body["sources"]} >= {"OpenAlex", "Crossref"}

        paper = body["papers"][0]
        for field in (
            "id", "title", "authors", "abstract", "year", "published_date", "doi",
            "arxiv_id", "paper_url", "pdf_url", "source", "citation_count", "journal",
            "venue", "keywords", "final_score", "relevance_score", "quality_score",
            "citation_score", "recency_score", "source_score", "overall_score", "rank",
        ):
            assert field in paper, f"missing contract field: {field}"

        assert paper["final_score"] == paper["overall_score"]
        assert paper["published_date"] == "2024-03-01"

    def test_unavailable_metadata_stays_null(self, client, stub_search):
        body = client.post(
            "/research", json={"query": "graph neural networks for molecular property prediction"}
        ).json()
        second = body["papers"][1]
        # No provider reported citations for this record → null, never invented.
        assert second["citation_count"] is None
        assert second["citation_score"] is None
        assert second["abstract"] != ""

    @pytest.mark.parametrize("query", ["", "  ", "ab"])
    def test_invalid_queries_are_rejected_cleanly(self, client, query):
        response = client.post("/research", json={"query": query})
        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "validation_error"
        assert body["status"] == "error"
        assert "Traceback" not in response.text

    def test_year_and_source_filters_are_accepted(self, client, stub_search):
        response = client.post(
            "/research",
            json={
                "query": "graph neural networks",
                "year_from": 2020,
                "open_access_only": True,
                "sources": ["openalex", "arxiv"],
                "limit": 10,
            },
        )
        assert response.status_code == 200


class TestNormalisation:
    def test_dates_from_every_provider_shape(self):
        assert normalize_date("2024-03-01T10:20:30Z") == "2024-03-01"
        assert normalize_date([[2024, 3, 1]]) == "2024-03-01"
        assert normalize_date([[2021]]) == "2021"
        assert normalize_date("2023 Mar 15") == "2023-03-15"
        assert normalize_date("2020") == "2020"
        assert normalize_date("not a date") is None
        assert normalize_date(None) is None

    def test_year_validation(self):
        assert normalize_year(2024) == 2024
        assert normalize_year("2019") == 2019
        assert normalize_year(12) is None
        assert normalize_year(9999) is None
        assert normalize_year(None) is None

    def test_year_is_derived_from_date(self):
        paper = normalizer_build_paper(
            title="Dated Paper", source="Crossref", published_date=[[2024, 5, 2]]
        )
        assert paper.year == 2024
        assert paper.published_date == "2024-05-02"

    def test_missing_metadata_is_never_invented(self):
        paper = build_paper(title="Sparse Record", source="arXiv")
        assert paper.doi is None
        assert paper.citation_count is None
        assert paper.journal is None
        assert paper.published_date is None
        assert paper.year is None
        assert paper.authors == []
        assert paper.abstract == ""

    def test_markup_and_control_characters_are_stripped(self):
        paper = build_paper(
            title="<jats:p>Graph   Networks</jats:p>\x00",
            source="Crossref",
            abstract="Line one\nLine two",
        )
        assert paper.title == "Graph Networks"
        assert "\x00" not in paper.title
        assert "\n" not in paper.abstract

    def test_author_and_keyword_lists_are_bounded_and_unique(self):
        paper = build_paper(
            title="Many Authors",
            source="Crossref",
            authors=["A One", "A One"] + [f"Author {i}" for i in range(60)],
            keywords=[f"kw{i}" for i in range(30)],
        )
        assert len(paper.authors) <= 40
        assert len(paper.authors) == len(set(paper.authors))
        assert len(paper.keywords) <= 12


class TestAnalysisEndpointContract:
    def test_missing_gemini_key_is_a_clear_503(self, client):
        response = client.post(
            "/analyze-paper",
            json={"title": "Graph Neural Networks for Drug Discovery", "abstract": "x" * 400},
        )
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["code"] == "missing_api_key"
        assert "GEMINI_API_KEY" in detail["message"]
        assert "unavailable because GEMINI_API_KEY is not configured" in detail["message"]

    def test_malformed_paper_input_is_rejected(self, client):
        for payload in (
            {},                                   # missing title
            {"title": "ab"},                      # too short
            {"title": "x" * 700},                 # too long
            {"title": "Valid Title", "year": "not-a-year"},
        ):
            response = client.post("/analyze-paper", json=payload)
            assert response.status_code == 422, payload
            assert "Traceback" not in response.text

    def test_invalid_pdf_url_scheme_is_refused(self, client, monkeypatch):
        import app.services.analysis_service as analysis_service
        from app.analysis.pdf_extractor import PDFError

        class ConfiguredClient:
            configured = True
            model = "stub"
            fallback_model = ""

        monkeypatch.setattr(analysis_service, "GeminiClient", lambda *a, **k: ConfiguredClient())

        def unsafe(*args, **kwargs):
            raise PDFError("Refused to download an unsafe URL", code="unsafe_url")

        monkeypatch.setattr("app.services.analysis_service.extract_pdf", unsafe)

        response = client.post(
            "/analyze-paper",
            json={
                "title": "Paper With Bad PDF URL",
                "abstract": "x" * 400,
                "pdf_url": "http://127.0.0.1:8000/secret.pdf",
            },
        )
        assert response.status_code == 400
        assert "unsafe" in response.json()["detail"]["message"].lower()
