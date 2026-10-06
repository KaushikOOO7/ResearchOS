"""AI analysis endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.analysis.pdf_extractor import PDFError
from app.api.helpers import ai_error_to_http, analysis_error_to_http, pdf_error_to_http
from app.schemas.analysis import AnalyzePaperResponse, PaperInput
from app.services.analysis_service import AnalysisError, analyze_paper_reference
from app.services.gemini_client import AIProviderError
from app.utils.logging_setup import get_logger

logger = get_logger("analysis-api")

router = APIRouter(tags=["analysis"])


@router.post("/analyze-paper", response_model=AnalyzePaperResponse)
def analyze_paper_endpoint(paper: PaperInput) -> AnalyzePaperResponse:
    """
    Download, extract and analyse one paper.

    Returns a structured analysis with provenance metadata (pages read,
    characters analysed, whether the abstract was used instead of full text).
    """
    try:
        result = analyze_paper_reference(paper)
    except PDFError as exc:
        status, payload = pdf_error_to_http(exc)
        logger.info("Analyze request failed (%s): %s", exc.code, str(exc)[:160])
        raise HTTPException(status_code=status, detail=payload.model_dump()) from exc
    except AnalysisError as exc:
        status, payload = analysis_error_to_http(exc)
        logger.info("Analyze request rejected (%s): %s", exc.code, str(exc)[:160])
        raise HTTPException(status_code=status, detail=payload.model_dump()) from exc
    except AIProviderError as exc:
        status, payload = ai_error_to_http(exc)
        logger.info("AI analysis failed (%s): %s", exc.code, str(exc)[:160])
        raise HTTPException(status_code=status, detail=payload.model_dump()) from exc
    except Exception as exc:  # noqa: BLE001 - last-resort guard
        logger.error("Unexpected analysis error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "code": "internal_error",
                "message": "Something went wrong while analysing this paper. Please try again.",
                "retryable": True,
            },
        ) from exc

    return result
