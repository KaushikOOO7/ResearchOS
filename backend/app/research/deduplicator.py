"""Paper deduplication and metadata merging."""

import re
from typing import Dict, List, Set, Tuple
from app.schemas.paper import Paper
from app.research.normalizer import clean_doi, clean_arxiv_id


def _title_fingerprint(title: str) -> str:
    """Generate a simplified alphanumeric lowercase fingerprint for exact fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _title_tokens(title: str) -> Set[str]:
    """Tokenize title into significant alphanumeric words."""
    words = re.findall(r"[a-z0-9]{3,}", title.lower())
    # Exclude common stop words
    stop_words = {"the", "and", "for", "with", "from", "that", "this", "via", "using", "into"}
    return {w for w in words if w not in stop_words}


def _titles_are_fuzzy_match(t1: str, t2: str, threshold: float = 0.85) -> bool:
    """Compare two titles using token-based Jaccard similarity."""
    tokens1 = _title_tokens(t1)
    tokens2 = _title_tokens(t2)
    if not tokens1 or not tokens2:
        return False
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    return (intersection / union) >= threshold


def _merge_paper_records(primary: Paper, secondary: Paper) -> Paper:
    """Merge secondary paper's metadata into primary if primary lacks it."""
    # Preferred longer abstract
    if len(secondary.abstract or "") > len(primary.abstract or ""):
        primary.abstract = secondary.abstract

    # Citation count
    if primary.citation_count is None and secondary.citation_count is not None:
        primary.citation_count = secondary.citation_count

    # PDF URL
    if not primary.pdf_url and secondary.pdf_url:
        primary.pdf_url = secondary.pdf_url

    # DOI
    if not primary.doi and secondary.doi:
        primary.doi = secondary.doi

    # arXiv ID
    if not primary.arxiv_id and secondary.arxiv_id:
        primary.arxiv_id = secondary.arxiv_id

    # Year
    if not primary.year and secondary.year:
        primary.year = secondary.year

    # Journal / Venue
    if not primary.journal and secondary.journal:
        primary.journal = secondary.journal
    if not primary.venue and secondary.venue:
        primary.venue = secondary.venue

    # Authors: if primary has few authors, prefer more detailed list
    if len(secondary.authors) > len(primary.authors):
        primary.authors = secondary.authors

    # Keywords merge
    if secondary.keywords:
        combined = set(primary.keywords) | set(secondary.keywords)
        primary.keywords = list(combined)

    return primary


def deduplicate_papers(papers: List[Paper]) -> List[Paper]:
    """
    Deduplicate a list of candidate papers preserving order of arrival.
    Matches against:
    1. Cleaned DOI
    2. Cleaned arXiv ID
    3. Normalized title fingerprint
    4. Fuzzy title token Jaccard similarity
    """
    seen_dois: Dict[str, Paper] = {}
    seen_arxivs: Dict[str, Paper] = {}
    seen_fingerprints: Dict[str, Paper] = {}
    unique_papers: List[Paper] = []

    for paper in papers:
        matched_existing: Optional[Paper] = None

        # 1. Match by DOI
        if paper.doi:
            norm_doi = clean_doi(paper.doi)
            if norm_doi and norm_doi in seen_dois:
                matched_existing = seen_dois[norm_doi]

        # 2. Match by arXiv ID
        if not matched_existing and paper.arxiv_id:
            norm_arxiv = clean_arxiv_id(paper.arxiv_id)
            if norm_arxiv and norm_arxiv in seen_arxivs:
                matched_existing = seen_arxivs[norm_arxiv]

        # 3. Match by exact title fingerprint
        title_fp = _title_fingerprint(paper.title)
        if not matched_existing and title_fp and title_fp in seen_fingerprints:
            matched_existing = seen_fingerprints[title_fp]

        # 4. Match by fuzzy title similarity among existing papers
        if not matched_existing and len(paper.title) > 15:
            for existing in unique_papers:
                if _titles_are_fuzzy_match(paper.title, existing.title):
                    matched_existing = existing
                    break

        if matched_existing:
            # Merge information into existing paper
            _merge_paper_records(matched_existing, paper)
        else:
            # New unique paper
            unique_papers.append(paper)
            if paper.doi:
                norm_doi = clean_doi(paper.doi)
                if norm_doi:
                    seen_dois[norm_doi] = paper
            if paper.arxiv_id:
                norm_arxiv = clean_arxiv_id(paper.arxiv_id)
                if norm_arxiv:
                    seen_arxivs[norm_arxiv] = paper
            if title_fp:
                seen_fingerprints[title_fp] = paper

    return unique_papers
