"""
Shared API helpers: friendly error mapping and payload builders.

The API never returns a raw stack trace to users. Internal detail is logged
server-side; clients receive a stable ``code``, a human message and whether a
retry could help.
"""

from __future__ import annotations

from typing import List, Tuple

from app.analysis.pdf_extractor import PDFError
from app.research.base import SourceOutcome
from app.research.search_engine import SearchOutcome
from app.schemas.common import ErrorResponse
from app.schemas.research import ResearchResponse
from app.services.analysis_service import AnalysisError
from app.services.gemini_client import AIProviderError
from app.utils.logging_setup import get_logger

logger = get_logger("api")


def pdf_error_to_http(exc: PDFError) -> Tuple[int, ErrorResponse]:
    """Map a PDF failure to ``(status_code, ErrorResponse)``."""
    mapping = {
        "unsafe_url": 400,
        "not_a_pdf": 422,
        "invalid_pdf": 422,
        "encrypted": 422,
        "too_large": 413,
        "not_found": 404,
        "forbidden": 403,
        "empty": 502,
        "network": 503,
        "timeout": 504,
    }
    status = mapping.get(exc.code, 502)
    return status, ErrorResponse(
        code=exc.code,
        message=str(exc),
        retryable=exc.retryable,
    )


def ai_error_to_http(exc: AIProviderError) -> Tuple[int, ErrorResponse]:
    """Map an AI provider failure to ``(status_code, ErrorResponse)``."""
    mapping = {
        "missing_api_key": 503,
        "sdk_missing": 503,
        "model_not_configured": 503,
        "rate_limited": 429,
        "unavailable": 503,
        "network": 503,
        "auth_error": 502,
        "model_not_found": 502,
        "bad_request": 422,
        "empty_response": 502,
        "invalid_json": 502,
        "ai_error": 502,
    }
    status = mapping.get(exc.code, 502)
    return status, ErrorResponse(
        code=exc.code,
        message=str(exc),
        retryable=exc.retryable,
    )


def analysis_error_to_http(exc: AnalysisError) -> Tuple[int, ErrorResponse]:
    status = 422 if exc.code == "insufficient_content" else 500
    return status, ErrorResponse(code=exc.code, message=str(exc), retryable=exc.retryable)


def build_research_response(outcome: SearchOutcome, query: str) -> ResearchResponse:
    """Convert a :class:`SearchOutcome` into the public API payload."""
    from app.models.paper import SourceStatus

    return ResearchResponse(
        status="success" if outcome.papers else "empty",
        message=outcome.message,
        query=query,
        query_analysis=outcome.query_analysis,
        stats=outcome.stats,
        sources=[
            SourceStatus(
                name=source.name,
                ok=source.ok,
                result_count=source.result_count,
                elapsed_ms=source.elapsed_ms,
                error=source.error,
                configured=source.configured,
            )
            for source in outcome.source_outcomes
        ],
        weights=outcome.weights.as_dict(),
        ranking_notes=outcome.notes,
        papers=[paper.to_public_dict() for paper in outcome.papers],
    )


def summarize_sources(outcomes: List[SourceOutcome]) -> str:
    """Short one-line provider summary for logs."""
    return ", ".join(
        f"{outcome.name}:{outcome.result_count if outcome.ok else 'failed'}"
        for outcome in outcomes
    )
