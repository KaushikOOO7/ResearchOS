"""
ResearchOS - AI Research Intelligence Platform
FastAPI Backend Application
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure backend root is in sys.path regardless of execution working directory
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.schemas.paper import (
    ResearchRequest,
    ResearchResponse,
    AnalyzePaperRequest,
    AnalyzePaperResponse,
    AnalysisResult,
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    GapSynthesisRequest,
    GapSynthesisResponse,
    ExperimentDesignRequest,
    ExperimentDesignResponse,
    ProjectBlueprintRequest,
    ProjectBlueprintResponse,
    HealthResponse,
)
from app.research.engine import execute_multi_provider_search, get_source_coverage
from app.analysis.pdf_extractor import extract_pdf_text
from app.analysis.paper_analyzer import analyze_paper, is_gemini_configured
from app.analysis.batch_processor import execute_batch_analysis
from app.analysis.synthesis import synthesize_research_gaps
from app.analysis.experiment_designer import design_experiment_for_gap
from app.analysis.blueprint_builder import generate_project_blueprint

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="[ResearchOS] %(levelname)s: %(message)s")
logger = logging.getLogger("researchos.main")

app = FastAPI(
    title="ResearchOS API",
    description="AI Research Intelligence & Scientific Discovery Platform Backend",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------

default_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

env_origins = os.getenv("CORS_ORIGINS", "")
if env_origins:
    custom_origins = [orig.strip() for orig in env_origins.split(",") if orig.strip()]
    allowed_origins = list(set(default_origins + custom_origins))
else:
    allowed_origins = default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_error = errors[0]["msg"] if errors else "Invalid request data"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"status": "error", "message": f"Validation error: {first_error}"},
    )


# ---------------------------------------------------------------------------
# Health & Status Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
def root():
    return {
        "project": "ResearchOS",
        "tagline": "From Research Ideas to Evidence-Driven Discoveries",
        "status": "running",
        "service": "ResearchOS API",
        "version": "1.0.0",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def health():
    return HealthResponse(
        status="healthy",
        service="ResearchOS API",
        version="1.0.0",
        gemini_configured=is_gemini_configured(),
    )


@app.get("/sources", tags=["Sources"])
@app.get("/api/sources", tags=["Sources"])
def sources_endpoint(query: str = ""):
    """Return live status of integrated providers and outbound academic portals."""
    return {"status": "success", "coverage": get_source_coverage(query)}


# ---------------------------------------------------------------------------
# Academic Research Search Endpoints (Top 30 Real Papers)
# ---------------------------------------------------------------------------

@app.post("/research", response_model=ResearchResponse, tags=["Research"])
@app.post("/api/research", response_model=ResearchResponse, tags=["Research"])
def search_papers(request: ResearchRequest):
    """
    Search academic repositories (arXiv, OpenAlex, Crossref, Semantic Scholar, PubMed).
    Returns top 30 ranked, deduplicated research papers.
    """
    logger.info("Received search query: '%s'", request.query)

    try:
        papers, queried, succeeded = execute_multi_provider_search(
            query=request.query,
            target_count=request.max_results,
        )

        return ResearchResponse(
            status="success",
            query=request.query,
            count=len(papers),
            papers=papers,
            providers_queried=queried,
            providers_succeeded=succeeded,
        )
    except Exception as e:
        logger.error("Academic search error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to complete research search: {str(e)}",
        )


# ---------------------------------------------------------------------------
# Individual AI Paper Analysis Endpoints
# ---------------------------------------------------------------------------

@app.post("/analyze-paper", response_model=AnalyzePaperResponse, tags=["Analysis"])
@app.post("/api/analyze-paper", response_model=AnalyzePaperResponse, tags=["Analysis"])
def analyze_paper_endpoint(request: AnalyzePaperRequest):
    """
    Analyze research paper text across 13 scientific dimensions.
    Extracts paper text from PDF (with SSRF protection) with fallback to abstract.
    """
    logger.info("Analyzing paper: '%s'", request.title)

    paper_text = ""
    evidence_basis = "Full-text analysis"

    if request.pdf_url:
        try:
            logger.info("Downloading and extracting PDF from %s", request.pdf_url)
            paper_text = extract_pdf_text(request.pdf_url)
            evidence_basis = "Full-text analysis"
        except Exception as pdf_err:
            logger.warning("PDF extraction failed (%s). Proceeding with abstract fallback.", pdf_err)
            paper_text = request.abstract or ""
            evidence_basis = "Abstract-only analysis"
    else:
        paper_text = request.abstract or ""
        evidence_basis = "Abstract-only analysis"

    if not paper_text:
        paper_text = request.abstract or ""

    try:
        raw_analysis = analyze_paper(
            title=request.title,
            abstract=request.abstract or "",
            paper_text=paper_text,
        )
        raw_analysis["evidence_basis"] = evidence_basis
        analysis_obj = AnalysisResult(**raw_analysis)

        return AnalyzePaperResponse(
            status="success",
            title=request.title,
            analysis=analysis_obj,
        )
    except RuntimeError as gemini_err:
        err_msg = str(gemini_err)
        logger.error("Gemini paper analysis error: %s", err_msg)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "message": err_msg},
        )
    except Exception as exc:
        logger.error("Unexpected analysis error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": f"Analysis failed: {str(exc)}"},
        )


# ---------------------------------------------------------------------------
# Batch Analysis for Research Lab (up to 30 papers)
# ---------------------------------------------------------------------------

@app.post("/batch-analyze", response_model=BatchAnalyzeResponse, tags=["Analysis"])
@app.post("/api/batch-analyze", response_model=BatchAnalyzeResponse, tags=["Analysis"])
def batch_analyze_endpoint(request: BatchAnalyzeRequest):
    """
    Execute batch analysis for up to 30 papers with controlled concurrency.
    """
    logger.info("Starting batch analysis for %d papers", len(request.papers))
    res = execute_batch_analysis(request.papers, max_concurrent=request.max_concurrent)
    return res


# ---------------------------------------------------------------------------
# Cross-Paper Research Gap Synthesis & Contradiction Detection
# ---------------------------------------------------------------------------

@app.post("/synthesize-gaps", response_model=GapSynthesisResponse, tags=["Synthesis"])
@app.post("/api/synthesize-gaps", response_model=GapSynthesisResponse, tags=["Synthesis"])
def synthesize_gaps_endpoint(request: GapSynthesisRequest):
    """
    Synthesize high-confidence research gaps and contradictions across analyzed papers.
    """
    logger.info("Synthesizing research gaps for query: '%s'", request.query)
    return synthesize_research_gaps(request.query, request.papers)


# ---------------------------------------------------------------------------
# AI Experiment Designer
# ---------------------------------------------------------------------------

@app.post("/design-experiment", response_model=ExperimentDesignResponse, tags=["Experiments"])
@app.post("/api/design-experiment", response_model=ExperimentDesignResponse, tags=["Experiments"])
def design_experiment_endpoint(request: ExperimentDesignRequest):
    """
    Design a rigorous empirical experiment protocol for a selected research gap.
    """
    gap_title = request.gap.get("title", "Selected Gap")
    logger.info("Designing experiment for gap: '%s'", gap_title)
    return design_experiment_for_gap(request.gap, request.query or "", request.supporting_papers)


# ---------------------------------------------------------------------------
# Project Blueprint & Implementation Builder
# ---------------------------------------------------------------------------

@app.post("/generate-blueprint", response_model=ProjectBlueprintResponse, tags=["Projects"])
@app.post("/api/generate-blueprint", response_model=ProjectBlueprintResponse, tags=["Projects"])
def generate_blueprint_endpoint(request: ProjectBlueprintRequest):
    """
    Generate an actionable technical project blueprint with Mermaid diagram and pseudocode.
    """
    logger.info("Generating project blueprint for: '%s'", request.title or "Research Initiative")
    return generate_project_blueprint(
        gap_or_idea=request.gap_or_idea,
        title=request.title or "",
        supporting_papers=request.supporting_papers,
        available_compute=request.available_compute or "1x RTX 4090",
        timeline_weeks=request.timeline_weeks or 8,
    )


# ---------------------------------------------------------------------------
# Session Persistence Endpoints
# ---------------------------------------------------------------------------

DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
SESSIONS_FILE = DATA_DIR / "sessions.json"


def _read_sessions() -> List[Dict[str, Any]]:
    if not SESSIONS_FILE.exists():
        return []
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _write_sessions(sessions: List[Dict[str, Any]]) -> None:
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        logger.warning("Could not persist sessions to file: %s", e)


@app.get("/sessions", tags=["Sessions"])
@app.get("/api/sessions", tags=["Sessions"])
def list_sessions():
    """List saved research sessions."""
    return {"status": "success", "sessions": _read_sessions()}


@app.post("/sessions", tags=["Sessions"])
@app.post("/api/sessions", tags=["Sessions"])
def save_session(session: Dict[str, Any]):
    """Save or update a research session."""
    session_id = session.get("id") or str(len(_read_sessions()) + 1)
    session["id"] = session_id
    sessions = _read_sessions()
    sessions = [s for s in sessions if s.get("id") != session_id]
    sessions.insert(0, session)
    _write_sessions(sessions[:30])
    return {"status": "success", "session": session}
