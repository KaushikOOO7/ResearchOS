"""
API endpoint tests for ResearchOS FastAPI backend.
Uses FastAPI TestClient.
"""

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.paper import Paper

client = TestClient(app)


def test_root_endpoint():
    """Verify root GET / returns project metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "ResearchOS"
    assert data["status"] == "running"


def test_health_endpoint():
    """Verify GET /health returns service status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data


def test_api_health_endpoint():
    """Verify GET /api/health works identically to /health."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_invalid_search_empty_query():
    """Verify search rejects empty or whitespace query with 422."""
    response = client.post("/research", json={"query": "   "})
    assert response.status_code == 422
    assert "error" in response.json()["status"]


def test_invalid_search_missing_fields():
    """Verify search rejects payload without query."""
    response = client.post("/research", json={})
    assert response.status_code == 422


def test_valid_search_request():
    """Verify search returns formatted papers when engine succeeds."""
    mock_papers = [
        Paper(id="p1", title="Advances in Reinforcement Learning", year="2024")
    ]
    with patch("app.main.execute_multi_provider_search", return_value=(mock_papers, ["arXiv"], ["arXiv"])):
        response = client.post("/research", json={"query": "reinforcement learning", "max_results": 10})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] == 1
        assert len(data["papers"]) == 1
        assert data["papers"][0]["title"] == "Advances in Reinforcement Learning"


def test_invalid_analysis_empty_title():
    """Verify analyze-paper endpoint rejects empty title."""
    response = client.post("/analyze-paper", json={"title": "  ", "abstract": "Test abstract"})
    assert response.status_code == 422


def test_missing_gemini_api_key():
    """Verify missing Gemini API key returns HTTP 503 with helpful message without crashing."""
    with patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
        response = client.post("/analyze-paper", json={
            "title": "A Sample Paper",
            "abstract": "Sample abstract"
        })
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "error"
        assert "GEMINI_API_KEY" in data["message"] or "not configured" in data["message"]


def test_valid_structured_analysis_response():
    """Verify structured AI analysis response contains all required fields."""
    mock_analysis_dict = {
        "research_problem": "Reducing computational cost of LLMs",
        "existing_approach": "Full quadratic attention",
        "proposed_method": "Linear state space models",
        "architecture": "Structured state space stack",
        "dataset": "Pile dataset",
        "model_algorithm": "Mamba",
        "results": "Faster inference by 5x",
        "limitations": ["Memory bound during training"],
        "additional_technical_limitations": ["AI-inferred limitation: Context length saturation"],
        "why_approach_may_fail": ["Associative recall degradation"],
        "research_gap": {
            "author_stated_gaps": ["Hybrid architectures"],
            "ai_inferred_gaps": ["Scaling beyond 100B parameters"]
        },
        "possible_improvements": ["Sparse attention gating"],
        "new_research_direction": ["Long-context bio-sequences"],
        "overall_assessment": "Groundbreaking efficient alternative to Transformers",
        "evidence_basis": "Full-text analysis"
    }

    with patch("app.main.analyze_paper", return_value=mock_analysis_dict):
        response = client.post("/analyze-paper", json={
            "title": "Mamba: Linear-Time Sequence Modeling",
            "abstract": "State space models enable linear time sequence modeling."
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        analysis = data["analysis"]
        assert analysis["research_problem"] == "Reducing computational cost of LLMs"
        assert len(analysis["limitations"]) == 1
        assert len(analysis["research_gap"]["author_stated_gaps"]) == 1
        assert analysis["overall_assessment"] != ""


def test_batch_analyze_endpoint():
    """Verify batch analysis queues and completes papers."""
    mock_papers = [
        {"id": "p1", "title": "Paper 1", "abstract": "Abstract 1"},
        {"id": "p2", "title": "Paper 2", "abstract": "Abstract 2"}
    ]
    mock_analysis = {
        "research_problem": "Problem",
        "proposed_method": "Method",
        "limitations": [],
        "overall_assessment": "Good"
    }
    with patch("app.analysis.batch_processor.analyze_paper", return_value=mock_analysis):
        response = client.post("/batch-analyze", json={"papers": mock_papers})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["completed"] == 2
        assert len(data["results"]) == 2


def test_synthesize_gaps_endpoint():
    """Verify research gap synthesis endpoint produces structured gaps."""
    mock_papers = [
        {"title": "Paper A", "analysis": {"research_problem": "Prob A", "limitations": ["Lim A"]}},
        {"title": "Paper B", "analysis": {"research_problem": "Prob B", "limitations": ["Lim B"]}}
    ]
    response = client.post("/synthesize-gaps", json={"query": "quantum algorithms", "papers": mock_papers})
    assert response.status_code == 200
    data = response.json()
    assert "gaps" in data
    assert len(data["gaps"]) >= 1
    assert "title" in data["gaps"][0]


def test_design_experiment_endpoint():
    """Verify experiment designer endpoint produces structured experimental protocol."""
    gap = {"title": "Generalization under extreme shift", "description": "Models fail under shift"}
    response = client.post("/design-experiment", json={"gap": gap})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "hypothesis" in data["experiment"]
    assert "independent_variables" in data["experiment"]
    assert "evaluation_metrics" in data["experiment"]


def test_generate_blueprint_endpoint():
    """Verify project blueprint endpoint generates phased plan and pseudocode."""
    gap = {"title": "Efficient sparse state spaces", "description": "Scaling limits"}
    response = client.post("/generate-blueprint", json={"gap_or_idea": gap, "timeline_weeks": 8})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "implementation_phases" in data["blueprint"]
    assert "starter_pseudocode" in data["blueprint"]
    assert "feasibility_score" in data["blueprint"]


def test_session_persistence_endpoints():
    """Verify session save and retrieval."""
    test_session = {"id": "test-session-123", "title": "Quantum ML Investigation", "stage": "Synthesis"}
    save_res = client.post("/sessions", json=test_session)
    assert save_res.status_code == 200

    list_res = client.get("/sessions")
    assert list_res.status_code == 200
    sessions = list_res.json()["sessions"]
    assert any(s.get("id") == "test-session-123" for s in sessions)
