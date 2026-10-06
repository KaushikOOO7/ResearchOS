"""
Paper analysis orchestration.

    POST /analyze-paper
      -> validate paper reference
      -> download + extract PDF   (skipped when no PDF is available)
      -> fall back to abstract     (clearly flagged, never silently)
      -> send to the AI analyst
      -> validate + return structured analysis with provenance metadata

Failures are typed (``PDFError`` / ``AIProviderError``) so the API layer can
map them to correct HTTP statuses and friendly messages.
"""

from __future__ import annotations

import time
from typing import Optional

from app.analysis.paper_analyzer import analyze_paper as run_analysis
from app.analysis.pdf_extractor import PDFError, extract_pdf
from app.analysis.text_cleaner import compose_analysis_text, detect_sections
from app.config import settings
from app.models.paper import build_paper_id
from app.schemas.analysis import (
    AnalysisMetadata,
    AnalyzePaperResponse,
    PaperInput,
)
from app.services.cache import TTLCache
from app.services.gemini_client import AIProviderError, GeminiClient
from app.utils.logging_setup import get_logger

logger = get_logger("analysis")

#: Minimum abstract length (characters) accepted for abstract-only analysis.
_MIN_ABSTRACT_CHARS = 220

#: Extracted PDF text is cached (keyed by URL) so re-analysing a paper — or a
#: retry after an AI failure — does not download and parse the same file again.
_pdf_cache: TTLCache = TTLCache(max_entries=32, ttl_seconds=3600)


class AnalysisError(RuntimeError):
    """Raised when a paper cannot be analysed for non-provider reasons."""

    def __init__(self, message: str, code: str = "analysis_error", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def analyze_paper_reference(
    paper: PaperInput,
    client: Optional[GeminiClient] = None,
) -> AnalyzePaperResponse:
    """
    Run the complete analysis pipeline for one paper.

    The returned metadata records exactly what the model saw: page count,
    extracted characters, whether the text was truncated, which sections were
    detected, and whether the analysis fell back to the abstract.
    """
    started = time.perf_counter()
    warnings: list[str] = []

    client = client or GeminiClient()
    if not client.configured:
        raise AIProviderError(
            "AI analysis is unavailable because GEMINI_API_KEY is not configured on the "
            "server. Add it to backend/.env (or your host's environment variables) and "
            "restart the backend.",
            code="missing_api_key",
        )

    extracted_text = ""
    pages: Optional[int] = None
    extracted_chars: Optional[int] = None
    sections: list[str] = []
    abstract_only = False

    pdf_url = (paper.pdf_url or "").strip()

    if pdf_url:
        try:
            logger.info("PDF extraction started")
            cached_text = _pdf_cache.get(pdf_url)
            if cached_text is not None:
                logger.info("PDF text served from cache (%d characters)", len(cached_text))
                from app.analysis.pdf_extractor import ExtractedPDF
                from app.analysis.text_cleaner import detect_sections

                sections_map, _ = detect_sections(cached_text)
                pdf = ExtractedPDF(
                    text=cached_text,
                    pages=0,
                    analyzed_pages=0,
                    sections=sections_map,
                    warnings=[],
                    elapsed_ms=0,
                    source_url=pdf_url,
                )
            else:
                pdf = extract_pdf(pdf_url)
            warnings.extend(pdf.warnings)
            pages = pdf.pages
            extracted_chars = pdf.char_count
            sections = pdf.section_names

            if pdf.is_scanned:
                logger.info("PDF extraction produced too little text — using abstract")
                abstract_only = True
            else:
                abstract_only = False
                extracted_text = pdf.text
                _pdf_cache.set(pdf_url, pdf.text)
        except PDFError as exc:
            logger.info("PDF extraction failed (%s): %s", exc.code, str(exc)[:160])
            if exc.code in {"unsafe_url", "not_a_pdf", "too_large", "encrypted"}:
                raise
            warnings.append(f"Full text unavailable ({str(exc)}).")
            abstract_only = True
    else:
        abstract_only = True
        warnings.append(
            "No direct PDF link was provided for this paper, so the analysis is based on the "
            "abstract only."
        )

    if abstract_only and len((paper.abstract or "").strip()) < _MIN_ABSTRACT_CHARS:
        raise AnalysisError(
            "This paper has no downloadable full text and its abstract is too short to analyse "
            "reliably. Try another paper or open the source page.",
            code="insufficient_content",
        )

    if not abstract_only:
        document, truncated = compose_analysis_text(
            paper_text=extracted_text,
            abstract=paper.abstract or "",
            sections={name: "" for name in sections} and {},
            max_chars=settings.analysis_max_chars,
        )
    else:
        document, truncated = "", False

    if abstract_only:
        analysed_chars = len(paper.abstract or "")
    else:
        analysed_chars = len(document)

    # Re-run section detection data through the composer for labelled text.
    if not abstract_only:
        from app.analysis.text_cleaner import detect_sections

        section_map, _ = detect_sections(extracted_text)
        document, truncated = compose_analysis_text(
            paper_text=extracted_text,
            abstract=paper.abstract or "",
            sections=section_map,
            max_chars=settings.analysis_max_chars,
        )
        analysed_chars = len(document)
        sections = list(section_map.keys()) or sections
        if truncated:
            warnings.append(
                f"The paper is longer than the analysis budget "
                f"({settings.analysis_max_chars:,} characters), so the most relevant sections "
                "were prioritised."
            )

    logger.info("AI analysis started")
    try:
        result = run_analysis(
            title=paper.title,
            abstract=paper.abstract or "",
            paper_text=document,
            abstract_only=abstract_only,
            client=client,
        )
    except AIProviderError:
        raise
    logger.info("AI analysis completed")

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    return AnalyzePaperResponse(
        status="success",
        paper_id=paper.paper_id
        or build_paper_id(paper.doi, paper.arxiv_id, paper.title),
        title=paper.title,
        analysis=result.analysis,
        metadata=AnalysisMetadata(
            model=result.model,
            used_fallback_model=result.used_fallback,
            pdf_url=pdf_url or None,
            pages=pages,
            extracted_chars=extracted_chars,
            analysed_chars=analysed_chars,
            referenced_abstract_only=abstract_only,
            truncated=truncated,
            sections_detected=sections,
            elapsed_ms=elapsed_ms,
            warnings=warnings,
        ),
    )
