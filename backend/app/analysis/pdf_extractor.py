"""
PDF text extraction utility.

Downloads a PDF from a URL and extracts its text content using pypdf.
No API keys or external services are required.
"""

import io
import logging

import requests
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# Reasonable timeout (seconds) for the HTTP download.
_DOWNLOAD_TIMEOUT = 30


def extract_pdf_text(pdf_url: str) -> str:
    """
    Download a PDF from ``pdf_url`` and return its full text content.

    Parameters
    ----------
    pdf_url:
        A publicly reachable URL pointing to a PDF document.

    Returns
    -------
    str
        The concatenated text of every page in the PDF.

    Raises
    ------
    ValueError
        If ``pdf_url`` is empty or not a string.
    RuntimeError
        If the PDF cannot be downloaded or parsed.
    """
    if not isinstance(pdf_url, str) or not pdf_url.strip():
        raise ValueError("pdf_url must be a non-empty URL string.")

    # ------------------------------------------------------------------
    # 1. Download the PDF.
    # ------------------------------------------------------------------
    try:
        response = requests.get(
            pdf_url,
            timeout=_DOWNLOAD_TIMEOUT,
            headers={"User-Agent": "ResearchOS/0.1 (pdf_extractor)"},
        )
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"Failed to download PDF from {pdf_url}: {exc}"
        ) from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to download PDF from {pdf_url}: "
            f"HTTP {response.status_code}"
        )

    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" not in content_type and content_type:
        # Some servers serve PDFs without a PDF content-type; we still
        # attempt parsing but log a warning so failures are diagnosable.
        logger.warning(
            "Unexpected Content-Type %r for %s; attempting parse anyway.",
            content_type,
            pdf_url,
        )

    pdf_bytes = response.content
    if not pdf_bytes:
        raise RuntimeError(
            f"Empty response body when downloading PDF from {pdf_url}."
        )

    # ------------------------------------------------------------------
    # 2. Parse the PDF and extract text from every page.
    # ------------------------------------------------------------------
    try:
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to parse PDF from {pdf_url}: {exc}"
        ) from exc

    if len(reader.pages) == 0:
        raise RuntimeError(
            f"PDF from {pdf_url} contains no pages."
        )

    page_texts = []
    for index, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            # A single page failing should not abort the whole document.
            logger.warning(
                "Failed to extract text from page %d of %s: %s",
                index + 1,
                pdf_url,
                exc,
            )
            text = ""
        page_texts.append(text)

    full_text = "\n".join(page_texts).strip()
    if not full_text:
        raise RuntimeError(
            f"No extractable text found in PDF from {pdf_url}."
        )

    return full_text