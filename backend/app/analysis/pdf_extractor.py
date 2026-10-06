"""
PDF download + text extraction.

Security and robustness rules (project brief, section 33):
  * URLs are validated before fetching (SSRF protection),
  * downloads stream with a hard size cap and a timeout,
  * the Content-Type must look like a PDF (warn + attempt otherwise),
  * page text extraction is page-isolated: one bad page cannot kill the run,
  * non-extractable (scanned/image-only) PDFs are reported clearly instead of
    producing empty analysis,
  * everything is bounded by ``PDF_MAX_*`` environment settings.
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests
from pypdf import PdfReader

from app.analysis.text_cleaner import clean_pdf_text, detect_sections
from app.config import settings
from app.utils.http import UnsafeUrlError, USER_AGENT, validate_public_url
from app.utils.logging_setup import get_logger

logger = get_logger("pdf")

#: Below this many extracted characters we assume the PDF is image-only.
_MIN_USABLE_CHARS = 400

_CHUNK_SIZE = 64 * 1024


class PDFError(RuntimeError):
    """Raised when a PDF cannot be downloaded or parsed."""

    def __init__(self, message: str, code: str = "pdf_error", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass
class ExtractedPDF:
    """Result of downloading and parsing a PDF."""

    text: str
    pages: int
    analyzed_pages: int
    sections: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    elapsed_ms: int = 0
    source_url: Optional[str] = None

    @property
    def char_count(self) -> int:
        return len(self.text or "")

    @property
    def is_scanned(self) -> bool:
        return self.char_count < _MIN_USABLE_CHARS

    @property
    def section_names(self) -> List[str]:
        return list(self.sections.keys())


def download_pdf_bytes(
    pdf_url: str,
    max_bytes: Optional[int] = None,
    timeout: Optional[float] = None,
) -> bytes:
    """
    Safely download a PDF and return its bytes.

    Raises :class:`PDFError` (never a bare requests exception) so callers can
    map failures to friendly messages.
    """
    max_bytes = max_bytes or settings.pdf_max_bytes
    timeout = timeout or settings.pdf_download_timeout

    try:
        safe_url = validate_public_url(pdf_url, provider="pdf")
    except UnsafeUrlError as exc:
        raise PDFError(f"Refused to download an unsafe URL: {exc}", code="unsafe_url") from exc

    try:
        response = requests.get(
            safe_url,
            timeout=(6.0, timeout),
            headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*;q=0.8"},
            stream=True,
        )
    except requests.exceptions.Timeout as exc:
        raise PDFError("The PDF download timed out.", code="timeout", retryable=True) from exc
    except requests.exceptions.RequestException as exc:
        raise PDFError(
            f"Could not download the PDF ({type(exc).__name__}).", code="network", retryable=True
        ) from exc

    with response:
        if response.status_code == 403:
            raise PDFError(
                "The publisher refused automated access to this PDF (HTTP 403).",
                code="forbidden",
            )
        if response.status_code == 404:
            raise PDFError("The PDF is not available at this URL (HTTP 404).", code="not_found")
        if response.status_code >= 400:
            raise PDFError(
                f"The PDF could not be downloaded (HTTP {response.status_code}).",
                code="http_error",
                retryable=response.status_code >= 500,
            )

        content_type = (response.headers.get("Content-Type") or "").lower()
        if content_type and "pdf" not in content_type and "octet-stream" not in content_type:
            # Some repositories mislabel PDFs; keep going but record it.
            logger.info("Unexpected Content-Type %s for %s", content_type, safe_url[:80])

        declared_size = response.headers.get("Content-Length")
        if declared_size and declared_size.isdigit() and int(declared_size) > max_bytes:
            raise PDFError(
                f"The PDF is too large ({int(declared_size) // (1024 * 1024)} MB > "
                f"{max_bytes // (1024 * 1024)} MB limit).",
                code="too_large",
            )

        buffer = io.BytesIO()
        total = 0
        for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise PDFError(
                    f"The PDF exceeds the {max_bytes // (1024 * 1024)} MB size limit.",
                    code="too_large",
                )
            buffer.write(chunk)

    data = buffer.getvalue()
    if not data:
        raise PDFError("The PDF download returned an empty file.", code="empty", retryable=True)

    # A valid PDF always starts with the %PDF- magic number.
    if not data[:5].startswith(b"%PDF"):
        raise PDFError(
            "The downloaded file is not a PDF (missing %PDF header).",
            code="not_a_pdf",
        )
    return data


def extract_text_from_bytes(data: bytes, source_url: Optional[str] = None) -> ExtractedPDF:
    """Parse PDF bytes into cleaned text, sections and telemetry."""
    started = time.perf_counter()
    warnings: List[str] = []

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - pypdf raises many exception types
        raise PDFError(f"The PDF could not be parsed: {type(exc).__name__}", code="invalid_pdf") from exc

    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")  # many PDFs are "encrypted" with an empty password
        except Exception:  # noqa: BLE001
            raise PDFError("The PDF is password protected.", code="encrypted")

    try:
        page_count = len(reader.pages)
    except Exception as exc:  # noqa: BLE001
        raise PDFError("The PDF has no readable pages.", code="invalid_pdf") from exc

    if page_count == 0:
        raise PDFError("The PDF contains no pages.", code="empty")

    max_pages = max(1, settings.pdf_max_pages)
    if page_count > max_pages:
        warnings.append(
            f"Only the first {max_pages} of {page_count} pages were processed "
            "(PDF_MAX_PAGES limit)."
        )

    page_texts: List[str] = []
    failed_pages = 0
    for index, page in enumerate(reader.pages[:max_pages]):
        try:
            page_texts.append(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001 - isolate per page
            failed_pages += 1
            logger.info("PDF page %d extraction failed: %s", index + 1, type(exc).__name__)
            page_texts.append("")

    if failed_pages:
        warnings.append(f"{failed_pages} page(s) could not be read.")

    raw_text = "\n".join(page_texts)
    cleaned = clean_pdf_text(raw_text)

    if len(cleaned) < _MIN_USABLE_CHARS:
        warnings.append(
            "Very little text could be extracted — this PDF is probably scanned "
            "or image-only, so the analysis will rely on the abstract."
        )

    sections, section_names = detect_sections(cleaned)
    if section_names:
        logger.info("Sections detected: %s", ", ".join(section_names))
    else:
        warnings.append("No standard paper sections could be detected in the text.")

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return ExtractedPDF(
        text=cleaned,
        pages=page_count,
        analyzed_pages=min(page_count, max_pages),
        sections=sections,
        warnings=warnings,
        elapsed_ms=elapsed_ms,
        source_url=source_url,
    )


def extract_pdf(pdf_url: str) -> ExtractedPDF:
    """Download and parse a PDF from ``pdf_url``."""
    logger.info("PDF download started")
    data = download_pdf_bytes(pdf_url)
    logger.info("PDF downloaded (%.1f KB)", len(data) / 1024)
    result = extract_text_from_bytes(data, source_url=pdf_url)
    logger.info(
        "PDF extraction completed — %d pages, %d characters, %d sections",
        result.pages,
        result.char_count,
        len(result.sections),
    )
    return result


def extract_pdf_text(pdf_url: str) -> str:
    """
    Backwards-compatible helper: return only the cleaned text of a PDF.

    Kept because it is the simplest possible API for scripts and tests; the
    service layer uses :func:`extract_pdf` for full telemetry.
    """
    return extract_pdf(pdf_url).text
