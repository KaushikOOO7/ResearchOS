"""
Cross-source deduplication.

The same paper routinely appears in arXiv, OpenAlex, Crossref and Semantic
Scholar. ResearchOS collapses those records into a single entry, keeping the
best metadata from each copy.

Match strategies, in order of confidence:
  1. identical DOI (after normalisation)
  2. identical arXiv id (version suffix stripped)
  3. identical normalised title
  4. fuzzy title match (token-set similarity >= threshold) *with*
     corroborating signals (same year ±1, or shared first-author surname)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.models.paper import Paper
from app.utils.logging_setup import get_logger
from app.utils.text import (
    normalize_arxiv_id,
    normalize_doi,
    normalize_title,
    token_containment,
    token_set_ratio,
)

logger = get_logger("dedupe")

#: Fuzzy title-match threshold (character-level). Academic titles that differ
#: only by a subtitle or a plural still match; genuinely different papers
#: almost never reach 0.92.
TITLE_SIMILARITY_THRESHOLD = 0.92

#: Token-containment required *in addition* to the character threshold. This
#: blocks the classic false positive where two different papers share a
#: template title and differ by a number or a word ("Study 1" / "Study 2").
#: Trade-off: a very long subtitle variant may be missed and shown twice,
#: which is preferable to silently merging two distinct papers.
TITLE_CONTAINMENT_THRESHOLD = 0.85

#: Title equality is only trusted for reasonably long titles, to avoid
#: merging short generic titles like "Editorial" or "Introduction".
MIN_TITLE_LENGTH_FOR_EXACT_MATCH = 18


def _first_author_surname(paper: Paper) -> str:
    if not paper.authors:
        return ""
    parts = [part for part in paper.authors[0].replace(".", " ").split() if part]
    return parts[-1].lower() if parts else ""


def _prefer(a: Optional[str], b: Optional[str]) -> Optional[str]:
    """Return the better of two optional strings (longer non-empty wins)."""
    if not a:
        return b
    if not b:
        return a
    return a if len(a) >= len(b) else b


class _UnionFind:
    """Tiny union-find used to group duplicate clusters."""

    def __init__(self, size: int):
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: int, b: int) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self.parent[root_b] = root_a


def _source_rank(paper: Paper) -> Tuple[int, float]:
    """
    Sort key for choosing a cluster's primary source.

    Prefers the record from the most complete metadata source (OpenAlex /
    Crossref tier) and, on a tie, the higher metadata score.
    """
    tier_weights = {"OpenAlex": 0, "Crossref": 1, "PubMed": 2, "Semantic Scholar": 3, "arXiv": 4}
    for index, source in enumerate(paper.sources or [paper.source]):
        if source in tier_weights:
            return (tier_weights[source], -paper.source_score)
    return (9, -paper.source_score)


def merge_papers(papers: List[Paper]) -> Paper:
    """
    Merge a duplicate cluster into one record.

    Field rules (documented so ranking stays explainable):
      * citations  -> highest reported value (different sources lag differently)
      * abstract   -> longest available
      * year       -> first non-null (sources rarely disagree by more than 1)
      * pdf_url    -> first available, preferring an arXiv/OpenAlex OA copy
      * keywords / subjects / sources -> union
      * quality/score fields -> recomputed later by the ranker
    """
    ordered = sorted(papers, key=_source_rank)
    primary = ordered[0].model_copy(deep=True)

    for other in ordered[1:]:
        primary.title = _prefer(primary.title, other.title) or primary.title
        primary.abstract = _prefer(primary.abstract, other.abstract) or ""
        primary.doi = primary.doi or other.doi
        primary.arxiv_id = primary.arxiv_id or other.arxiv_id
        primary.venue = (
            primary.venue
            if primary.venue and "arxiv" not in primary.venue.lower()
            else (other.venue or primary.venue)
        )
        primary.paper_url = primary.paper_url or other.paper_url
        primary.published_date = primary.published_date or other.published_date
        primary.journal = (
            primary.journal
            if primary.journal and "arxiv" not in primary.journal.lower()
            else (other.journal or primary.journal)
        )
        primary.pdf_url = primary.pdf_url or other.pdf_url
        primary.year = primary.year or other.year
        primary.type = primary.type or other.type

        if other.citation_count is not None:
            if primary.citation_count is None or other.citation_count > primary.citation_count:
                primary.citation_count = other.citation_count

        if primary.is_open_access is None:
            primary.is_open_access = other.is_open_access
        elif other.is_open_access:
            primary.is_open_access = True

        if len(other.authors) > len(primary.authors):
            primary.authors = list(other.authors)

        for keyword in other.keywords:
            if keyword not in primary.keywords:
                primary.keywords.append(keyword)
        for subject in other.subjects:
            if subject not in primary.subjects:
                primary.subjects.append(subject)
        for source in other.sources or [other.source]:
            if source and source not in primary.sources:
                primary.sources.append(source)

    # `source` reflects the record we took metadata from; `sources` lists all.
    primary.source = ordered[0].source
    primary.sources = [s for s in dict.fromkeys(primary.sources) if s]
    primary.id = ordered[0].id

    # Recompute the id so merged records stay reachable by DOI even when the
    # primary record was title-only.
    from app.models.paper import build_paper_id

    merged_id = build_paper_id(primary.doi, primary.arxiv_id, primary.title)
    primary.id = merged_id
    return primary


def deduplicate(papers: List[Paper]) -> Tuple[List[Paper], int]:
    """
    Collapse duplicates and return ``(unique_papers, removed_count)``.

    Deterministic: input order defines output order of clusters.
    """
    if not papers:
        return [], 0

    index = _UnionFind(len(papers))
    by_doi: Dict[str, int] = {}
    by_arxiv: Dict[str, int] = {}
    by_title: Dict[str, int] = {}

    for position, paper in enumerate(papers):
        doi = normalize_doi(paper.doi)
        if doi:
            if doi in by_doi:
                index.union(by_doi[doi], position)
            else:
                by_doi[doi] = position

        arxiv_id = normalize_arxiv_id(paper.arxiv_id)
        if arxiv_id:
            if arxiv_id in by_arxiv:
                index.union(by_arxiv[arxiv_id], position)
            else:
                by_arxiv[arxiv_id] = position

        title_key = normalize_title(paper.title)
        if title_key and len(title_key) >= MIN_TITLE_LENGTH_FOR_EXACT_MATCH:
            if title_key in by_title:
                index.union(by_title[title_key], position)
            else:
                by_title[title_key] = position

    # Fuzzy pass: bucket by first 24 characters of the normalised title so we
    # only compare plausible pairs (O(n·k) instead of O(n²)).
    buckets: Dict[str, List[int]] = {}
    for position, paper in enumerate(papers):
        title_key = normalize_title(paper.title)
        if not title_key:
            continue
        buckets.setdefault(title_key[:24], []).append(position)

    for bucket in buckets.values():
        if len(bucket) < 2:
            continue
        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                a, b = bucket[i], bucket[j]
                if index.find(a) == index.find(b):
                    continue
                title_a = normalize_title(papers[a].title)
                title_b = normalize_title(papers[b].title)
                if token_set_ratio(title_a, title_b) < TITLE_SIMILARITY_THRESHOLD:
                    continue
                if token_containment(title_a, title_b) < TITLE_CONTAINMENT_THRESHOLD:
                    continue
                if not _corroborates(papers[a], papers[b]):
                    continue
                index.union(a, b)

    clusters: Dict[int, List[Paper]] = {}
    order: List[int] = []
    for position, paper in enumerate(papers):
        root = index.find(position)
        if root not in clusters:
            clusters[root] = []
            order.append(root)
        clusters[root].append(paper)

    merged: List[Paper] = []
    for root in order:
        cluster = clusters[root]
        merged.append(cluster[0] if len(cluster) == 1 else merge_papers(cluster))

    removed = len(papers) - len(merged)
    if removed:
        logger.info(
            "Duplicates removed: %d (from %d candidates -> %d unique)",
            removed,
            len(papers),
            len(merged),
        )
    return merged, removed


def _corroborates(a: Paper, b: Paper) -> bool:
    """
    Secondary evidence required for a fuzzy title match.

    Either the years are compatible (within 1 year) or the first-author
    surnames match. Prevents merging unrelated papers that merely share a
    template-ish title.
    """
    if a.year and b.year and abs(a.year - b.year) <= 1:
        return True
    surname_a, surname_b = _first_author_surname(a), _first_author_surname(b)
    if surname_a and surname_b and surname_a == surname_b:
        return True
    # Strong title similarity with no contradicting evidence (both years
    # unknown) is still accepted.
    if not a.year and not b.year:
        return True
    return False
