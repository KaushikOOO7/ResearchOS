"""PDF extraction, cleaning, section detection and SSRF-guard tests."""

from __future__ import annotations

import pytest

from app.analysis.pdf_extractor import PDFError, extract_text_from_bytes
from app.analysis.text_cleaner import clean_pdf_text, compose_analysis_text, detect_sections
from app.utils.http import UnsafeUrlError, validate_public_url


class TestExtraction:
    def test_extracts_text_from_valid_pdf(self, pdf_factory):
        long_text = "Graph neural networks for molecular property prediction. " * 12
        result = extract_text_from_bytes(pdf_factory(long_text))
        assert result.pages == 1
        assert result.char_count > 20
        assert "Graph neural networks" in result.text
        assert result.is_scanned is False

    def test_multi_page_pdf_reports_page_count(self, pdf_factory):
        result = extract_text_from_bytes(pdf_factory("page content", pages=3))
        assert result.pages == 3
        assert result.analyzed_pages == 3

    def test_non_pdf_bytes_are_rejected(self):
        with pytest.raises(PDFError) as error:
            extract_text_from_bytes(b"this is definitely not a pdf")
        assert error.value.code == "invalid_pdf"

    def test_image_only_pdf_is_flagged_as_scanned(self, pdf_factory):
        result = extract_text_from_bytes(pdf_factory("x"))
        assert result.is_scanned is True
        assert any("scanned" in warning.lower() for warning in result.warnings)


class TestCleaning:
    def test_joins_hyphenated_line_breaks(self):
        cleaned = clean_pdf_text("distribu-\nted computing is useful")
        assert "distributed computing" in cleaned

    def test_removes_page_numbers_and_arxiv_stamps(self):
        raw = "Introduction\n12\narXiv:2401.01234v1 [cs.LG] 3 Jan 2024\nThe method works."
        cleaned = clean_pdf_text(raw)
        assert "arXiv:" not in cleaned
        assert "\n12\n" not in cleaned
        assert "Introduction" in cleaned

    def test_detects_standard_sections(self):
        text = (
            "1 Introduction\nGraphs are everywhere.\n\n"
            "2 Related Work\nPrior work used fingerprints.\n\n"
            "3 Methodology\nWe build a message passing network.\n\n"
            "4 Experiments\nWe evaluate on MoleculeNet.\n\n"
            "5 Conclusion\nWe conclude.\n\n"
            "References\n[1] Someone et al."
        )
        sections, names = detect_sections(text)
        assert {"introduction", "related_work", "methodology", "experiments", "conclusion"} <= set(names)
        assert "message passing" in sections["methodology"]

    def test_compose_analysis_text_labels_sections_and_truncates(self):
        sections = {"introduction": "Intro body " * 50, "methodology": "Method body " * 50}
        document, truncated = compose_analysis_text(
            paper_text="full text fallback",
            abstract="An abstract.",
            sections=sections,
            max_chars=300,
        )
        assert "## ABSTRACT" in document
        assert "## INTRODUCTION" in document
        assert truncated is True
        assert len(document) < 500


class TestUrlSafety:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.org/paper.pdf",
            "http://localhost/paper.pdf",
            "http://127.0.0.1/paper.pdf",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.5/paper.pdf",
            "http://192.168.1.10/paper.pdf",
            "http://[::1]/paper.pdf",
            "http://metadata.internal/paper.pdf",
        ],
    )
    def test_rejects_unsafe_urls(self, url):
        with pytest.raises(UnsafeUrlError):
            validate_public_url(url)

    def test_rejects_allowed_scheme_with_disallowed_host(self):
        with pytest.raises(UnsafeUrlError):
            validate_public_url("https://example.org:22/paper.pdf")

    def test_accepts_public_https_url(self, monkeypatch):
        import app.utils.http as http_module

        monkeypatch.setattr(
            http_module.socket,
            "getaddrinfo",
            lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
        )
        assert validate_public_url("https://example.org/paper.pdf").startswith("https://")
