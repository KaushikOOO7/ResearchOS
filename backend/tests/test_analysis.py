"""
Tests for PDF extraction and SSRF validation.
"""

from unittest.mock import patch, MagicMock
import pytest
from app.analysis.pdf_extractor import validate_url_security, extract_pdf_text, download_pdf_safely


def test_ssrf_blocks_private_and_metadata_ips():
    """Verify SSRF validation blocks loopback, private networks, and metadata endpoints."""
    blocked_urls = [
        "http://localhost:8000/internal",
        "http://127.0.0.1:8000/secret",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/admin",
        "http://192.168.1.1/router",
        "http://metadata.google.internal/computeMetadata/v1/",
        "ftp://example.com/paper.pdf",
    ]

    for url in blocked_urls:
        with pytest.raises(ValueError):
            validate_url_security(url)


def test_ssrf_permits_public_academic_url():
    """Verify safe public academic domains pass hostname resolution check."""
    # Test valid URL validation without raising
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("128.84.21.18", 443))]):
        validate_url_security("https://arxiv.org/pdf/2301.00001.pdf")


def test_pdf_download_failure():
    """Verify download error raises descriptive RuntimeError."""
    with patch("app.analysis.pdf_extractor.validate_url_security"), \
         patch("requests.get", side_effect=Exception("Connection refused")):
        with pytest.raises(RuntimeError) as exc_info:
            extract_pdf_text("https://example.com/broken.pdf")
        assert "Network error" in str(exc_info.value) or "Failed" in str(exc_info.value)


def test_malformed_pdf():
    """Verify corrupt/malformed PDF bytes raise RuntimeError without crashing process."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/pdf"}
    mock_response.iter_content.return_value = [b"This is not a real PDF file."]

    with patch("app.analysis.pdf_extractor.validate_url_security"), \
         patch("requests.get", return_value=mock_response):
        with pytest.raises(RuntimeError) as exc_info:
            extract_pdf_text("https://example.com/corrupt.pdf")
        assert "Failed to parse PDF document" in str(exc_info.value)
