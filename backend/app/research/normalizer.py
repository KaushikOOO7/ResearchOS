"""Paper metadata normalizer."""

import re
from typing import Any, Dict, List, Optional
from app.schemas.paper import Paper


def normalize_title(title: str) -> str:
    """Clean and normalize a title string for consistent display and comparison."""
    if not title:
        return ""
    # Strip whitespace, newlines, and trailing periods
    cleaned = re.sub(r"\s+", " ", title).strip()
    return cleaned


def clean_doi(doi: Optional[str]) -> Optional[str]:
    """Clean and normalize a DOI."""
    if not doi:
        return None
    doi_str = str(doi).strip()
    # Remove URL prefixes like https://doi.org/ or doi:
    doi_str = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi_str, flags=re.IGNORECASE)
    doi_str = re.sub(r"^doi:\s*", "", doi_str, flags=re.IGNORECASE)
    return doi_str.strip().lower() if doi_str.strip() else None


def clean_arxiv_id(arxiv_id: Optional[str]) -> Optional[str]:
    """Clean and normalize an arXiv ID."""
    if not arxiv_id:
        return None
    id_str = str(arxiv_id).strip()
    # Extract arXiv ID from URL or abs/ format
    id_str = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", id_str, flags=re.IGNORECASE)
    id_str = re.sub(r"(\.pdf|v\d+)$", "", id_str)  # strip version and .pdf extension
    return id_str.strip() if id_str.strip() else None


def build_paper_id(source: str, identifier: str) -> str:
    """Create a deterministic unique identifier for a paper."""
    sanitized_source = re.sub(r"[^a-zA-Z0-9]", "", source).lower()
    sanitized_id = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", identifier)
    return f"{sanitized_source}:{sanitized_id}"
