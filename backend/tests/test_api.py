"""API contract tests (FastAPI TestClient)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import app.services.analysis_service as analysis_service
from app.analysis.pdf_extractor import ExtractedPDF
from app.main import create_app
from app.models.paper import QueryAnalysis, SearchStats, SourceStatus
from app.research.base import build_paper
from app.research.search_engine import SearchOutcome
from app.services.cache import search_cache
from app.services.gemini_client import GenerationResult


@pytest.fixture
def client() -> TestClient:
    search_cache.clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    search_cache.clear()


@pytest.fixture
def fake_search(monkeypatch):
    """Replace the pipeline with a deterministic two-paper outcome."""
    papers = [
        build_paper(
            title="Graph Neural Networks for Molecular Property Prediction",
            abstract="graph neural networks for molecular property prediction",
            source="OpenAlex",
            year=2024,
            doi="10.1000/a",
            citation_count=120,
            doc_type="journal-article",
            venue="Journal of Cheminformatics",
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
    from app.research.ranker import rank_papers
    from app.research.query_understanding import analyze_query
    from app.config import RankingWeights

    analysis = analyze_query("graph neural networks for molecular property prediction")
    ranked = rank_papers(papers, analysis, RankingWeights())

    calls = {"count": 0}

    def fake_run_search(query, **kwargs):
        calls["count"] += 1
        return SearchOutcome(
            query_analysis=analysis,
            papers=ranked,
            source_outcomes=[
                SourceStatus(name="OpenAlex", ok=True, result_count=1, elapsed_ms=120),
                SourceStatus(name="Crossref", ok=True, result_count=1, elapsed_ms=90),
            ],
            stats=SearchStats(candidates_collected=4, duplicates_removed=2, returned=len(ranked)),
            notes=["test note"],
        )

    import app.api.research as research_api

    monkeypatch.setattr(research_api, "run_search", fake_run_search)
    return calls


class TestMetaEndpoints:
    def test_root(self, client):
        payload = client.get("/").json()
        assert payload["project"] == "ResearchOS"
        assert payload["status"] == "running"

    def test_health_reports_capabilities_without_secrets(self, client):
        payload = client.get("/health").json()
        assert payload["status"] == "healthy"
        assert payload["service"] == "ResearchOS"
        assert set(payload["providers"]) >= {"arxiv", "openalex", "crossref", "pubmed"}
        assert isinstance(payload["gemini_configured"], bool)
        # Never leak secret *values*: the payload may name environment
        # variables in human-readable warnings, but no credential material.
        assert "AIza" not in json.dumps(payload)  # Google API key prefix
        assert not any(
            isinstance(value, str) and len(value) > 80
            for value in payload["providers"].values()
        )

    def test_validation_error_is_friendly(self, client):
        response = client.post("/research", json={"query": "ab"})
        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "validation_error"
        assert "query" in body["message"]


class TestResearchEndpoint:
    def test_returns_ranked_papers_with_scores(self, client, fake_search):
        response = client.post(
            "/research", json={"query": "graph neural networks for molecular property prediction"}
        )
        assert response.status_code == 200
        body = response.json()

        assert body["status"] == "success"
        assert body["stats"]["candidates_collected"] == 4
        assert body["weights"]["relevance"] == pytest.approx(0.5)
        assert body["ranking_notes"]

        papers = body["papers"]
        assert len(papers) == 2
        first = papers[0]
        assert first["rank"] == 1
        assert first["relevance_score"] > papers[1]["relevance_score"]
        assert first["quality_label"] in {"High", "Medium", "Basic"}
        assert first["authors_display"]
        assert first["score_explanations"]["overall"].startswith("Overall")

    def test_results_are_cached(self, client, fake_search):
        payload = {"query": "graph neural networks for molecular property prediction"}
        client.post("/research", json=payload)
        client.post("/research", json=payload)
        assert fake_search["count"] == 1

    def test_unknown_paper_id_returns_404(self, client):
        response = client.get("/papers/p_deadbeefdeadbeef")
        assert response.status_code == 404
        assert "search again" in response.json()["detail"].lower()


class TestAnalyzeEndpoint:
    def test_missing_api_key_returns_friendly_503(self, client, monkeypatch):
        class NotConfigured:
            configured = False

        monkeypatch.setattr(analysis_service, "GeminiClient", lambda *a, **k: NotConfigured())

        response = client.post(
            "/analyze-paper",
            json={
                "title": "Graph Neural Networks for Drug Discovery",
                "abstract": "An abstract.",
                "pdf_url": "https://example.org/paper.pdf",
            },
        )
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["code"] == "missing_api_key"
        assert "GEMINI_API_KEY" in detail["message"]

    def test_full_analysis_flow_with_stubbed_ai(self, client, monkeypatch, pdf_factory):
        model_payload = {
            "research_problem": "Predict molecular properties with limited labels.",
            "existing_approach": "Fingerprint-based models.",
            "proposed_method": "A message passing GNN.",
            "architecture": "Encoder + readout.",
            "dataset": "MoleculeNet (as stated).",
            "model_algorithm": "MPNN with Adam.",
            "results": "RMSE improves by 8%.",
            "limitations": ["Author-stated limitation: single dataset."],
            "additional_technical_limitations": ["AI-inferred limitation: no OOD test."],
            "why_approach_may_fail": ["Distribution shift in scaffolds."],
            "research_gap": {
                "author_stated_gaps": ["Author-stated gap: no cross-domain transfer"],
                "ai_inferred_gaps": ["AI-inferred gap: uncertainty estimation"],
            },
            "possible_improvements": ["Add conformer features."],
            "new_research_direction": ["Test on protein-ligand complexes."],
            "overall_assessment": "Solid contribution with open questions.",
        }

        class StubClient:
            configured = True
            model = "stub-model"
            fallback_model = ""

            def generate_json(self, prompt, system_instruction=None, temperature=None):
                return GenerationResult(
                    text=json.dumps(model_payload), model="stub-model", attempts=1
                )

        intro = "Graphs are useful for chemistry. " * 12
        method = "We use message passing networks with readout functions. " * 12

        def fake_extract_pdf(url):
            return ExtractedPDF(
                text=f"1 Introduction\n{intro}\n\n3 Methodology\n{method}",
                pages=8,
                analyzed_pages=8,
                sections={"introduction": intro, "methodology": method},
                warnings=[],
                elapsed_ms=42,
                source_url=url,
            )

        monkeypatch.setattr(analysis_service, "GeminiClient", lambda *a, **k: StubClient())
        monkeypatch.setattr(analysis_service, "extract_pdf", fake_extract_pdf)

        response = client.post(
            "/analyze-paper",
            json={
                "title": "Graph Neural Networks for Molecular Property Prediction",
                "abstract": "We study graph neural networks for molecular property prediction "
                            "on public benchmarks, comparing message passing variants against "
                            "fingerprint baselines under identical splits.",
                "pdf_url": "https://example.org/paper.pdf",
                "source": "arXiv",
                "year": 2024,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body["analysis"]) == {
            "research_problem", "existing_approach", "proposed_method", "architecture",
            "dataset", "model_algorithm", "results", "limitations",
            "additional_technical_limitations", "why_approach_may_fail", "research_gap",
            "possible_improvements", "new_research_direction", "overall_assessment",
        }
        assert body["metadata"]["pages"] == 8
        assert body["metadata"]["referenced_abstract_only"] is False
        assert "introduction" in body["metadata"]["sections_detected"]
        assert body["analysis"]["limitations"][0].startswith("Author-stated limitation:")
        assert body["analysis"]["research_gap"]["ai_inferred_gaps"][0].startswith("AI-inferred gap:")
