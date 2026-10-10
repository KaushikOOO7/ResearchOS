"""
Secure PDF text extraction utility with SSRF protection and resource bounds.
"""

import io
import ipaddress
import logging
import socket
from typing import Optional
from urllib.parse import urlparse

import requests
from pypdf import PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger("researchos.pdf_extractor")

# Configuration constants
MAX_PDF_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_EXTRACTED_CHARS = 60000            # 60,000 characters
DOWNLOAD_TIMEOUT = 15                  # 15 seconds
MAX_REDIRECTS = 3
USER_AGENT = "ResearchOS/1.0 (academic-pdf-extractor; mailto:contact@researchos.dev)"


def validate_url_security(url: str) -> None:
    """
    Validate URL to protect against SSRF (Server-Side Request Forgery).
    Blocks private IP ranges, loopback, link-local, and cloud metadata endpoints.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL does not contain a valid hostname.")

    # Block common internal hostname names
    lower_host = hostname.lower()
    blocked_hosts = {
        "localhost", "127.0.0.1", "::1", "metadata.google.internal",
        "169.254.169.254", "instance-data", "metadata"
    }
    if lower_host in blocked_hosts or lower_host.endswith(".internal") or lower_host.endswith(".local"):
        raise ValueError("Access to internal or loopback hostnames is prohibited.")

    # Resolve IP addresses and check each
    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve hostname '{hostname}': {e}")

    for info in addr_info:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or str(ip) == "169.254.169.254"
            ):
                raise ValueError(f"Access to private or non-routable IP addresses ({ip_str}) is prohibited.")
        except ValueError as err:
            if "prohibited" in str(err):
                raise err
            # invalid IP string
            raise ValueError(f"Invalid IP address format resolved for {hostname}")


def download_pdf_safely(pdf_url: str) -> bytes:
    """Download PDF content safely with bounded size and validated redirect destinations."""
    current_url = pdf_url
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/pdf,application/octet-stream,*/*",
    }

    for redirect_count in range(MAX_REDIRECTS + 1):
        validate_url_security(current_url)

        try:
            response = requests.get(
                current_url,
                headers=headers,
                timeout=DOWNLOAD_TIMEOUT,
                stream=True,
                allow_redirects=False,
            )
        except (requests.exceptions.RequestException, Exception) as exc:
            raise RuntimeError(f"Network error while downloading PDF: {exc}") from exc

        # Handle redirects manually to validate redirect target IPs
        if response.status_code in (301, 302, 303, 307, 308):
            redirect_url = response.headers.get("Location")
            if not redirect_url:
                raise RuntimeError(f"HTTP {response.status_code} redirect without Location header.")
            # Resolve relative URLs
            if not redirect_url.startswith("http"):
                parsed_cur = urlparse(current_url)
                current_url = f"{parsed_cur.scheme}://{parsed_cur.netloc}/{redirect_url.lstrip('/')}"
            else:
                current_url = redirect_url
            continue

        if response.status_code != 200:
            raise RuntimeError(f"Failed to download PDF (HTTP {response.status_code}).")

        # Stream content up to MAX_PDF_SIZE_BYTES
        content_chunks = []
        downloaded_bytes = 0

        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                downloaded_bytes += len(chunk)
                if downloaded_bytes > MAX_PDF_SIZE_BYTES:
                    raise ValueError(f"PDF exceeds the maximum allowed file size of {MAX_PDF_SIZE_BYTES // (1024 * 1024)} MB.")
                content_chunks.append(chunk)

        pdf_bytes = b"".join(content_chunks)
        if not pdf_bytes:
            raise RuntimeError("The downloaded PDF file is empty.")

        # Check %PDF signature
        if not pdf_bytes.startswith(b"%PDF"):
            # Check within the first 1024 bytes in case of leading whitespace or comments
            if b"%PDF" not in pdf_bytes[:1024]:
                logger.warning("Downloaded file does not start with standard %%PDF header.")

        return pdf_bytes

    raise RuntimeError(f"Exceeded maximum allowed redirects ({MAX_REDIRECTS}).")


def extract_pdf_text(pdf_url: str) -> str:
    """
    Safely download and extract text content from an academic paper PDF.
    Returns cleaned text capped at 60,000 characters.
    """
    if not pdf_url or not isinstance(pdf_url, str):
        raise ValueError("A valid PDF URL string is required.")

    pdf_bytes = download_pdf_safely(pdf_url)

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except (PdfReadError, Exception) as exc:
        raise RuntimeError(f"Failed to parse PDF document: {exc}") from exc

    if reader.is_encrypted:
        try:
            # Try decrypting with empty password if encrypted
            reader.decrypt("")
        except Exception:
            raise RuntimeError("The requested PDF document is password-protected and cannot be analyzed.")

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise RuntimeError("The PDF contains no pages.")

    extracted_pages = []
    total_chars = 0

    for page_idx, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
        except Exception as e:
            logger.warning("Could not extract text from page %d: %s", page_idx + 1, e)
            page_text = ""

        if page_text:
            extracted_pages.append(page_text)
            total_chars += len(page_text)
            if total_chars >= MAX_EXTRACTED_CHARS:
                break

    full_text = "\n\n".join(extracted_pages).strip()
    if not full_text:
        raise RuntimeError("No extractable text was found in the PDF document (it may contain only scanned images).")

    return full_text[:MAX_EXTRACTED_CHARS]
