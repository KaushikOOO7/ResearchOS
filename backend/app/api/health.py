"""Health and capability endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.analysis.paper_analyzer import analyzer_status
from app.config import settings
from app.schemas.common import HealthResponse
from app.version import VERSION

router = APIRouter(tags=["health"])

_FEATURES = [
    "Multi-source search (arXiv, OpenAlex, Crossref, Semantic Scholar, PubMed)",
    "Cross-source deduplication",
    "Explainable relevance/quality/recency/citation ranking",
    "PDF text extraction with section detection",
    "Structured AI paper analysis (facts vs AI inference)",
]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """
    Report service health *and* which capabilities are active.

    The frontend uses this to tell the user, honestly, when AI analysis is
    unavailable (no API key) instead of failing at click time.
    """
    analysis = analyzer_status()
    summary = settings.public_summary()

    warnings = []
    if not analysis["configured"]:
        warnings.append(
            "AI analysis is disabled: GEMINI_API_KEY is not configured on the server."
        )
    for name, configured in summary["providers"].items():
        if not configured:
            warnings.append(f"Provider skipped (no credentials): {name}")

    return HealthResponse(
        status="healthy",
        service="ResearchOS",
        version=VERSION,
        environment=summary["environment"],
        gemini_configured=analysis["configured"],
        gemini_model=analysis["model"],
        providers=summary["providers"],
        features=_FEATURES,
        warnings=warnings,
    )
