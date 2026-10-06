"""
ResearchOS relevance & quality ranking.

Pipeline stage:

    candidates -> relevance -> quality -> recency -> citation -> source
               -> weighted overall -> ranked list

Design principles
-----------------
* **Explainable**: every component score is a documented, deterministic
  function of metadata, and each paper carries ``score_explanations``.
* **Honest**: a component that cannot be computed (e.g. citation counts for
  arXiv-only records) is ``None`` and is *left out of the weighted average*
  instead of being faked as zero.
* **Configurable**: weights come from ``RankingWeights`` (env-overridable).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Set, Tuple

from app.config import RankingWeights
from app.models.paper import Paper, QueryAnalysis
from app.utils.logging_setup import get_logger
from app.utils.text import normalize_title, significance_tokens, stem

logger = get_logger("ranker")

# --- BM25 hyper-parameters -------------------------------------------------
_BM25_K1 = 1.2
_BM25_B = 0.75

# --- Field weights used to build the BM25 document -------------------------
_FIELD_WEIGHTS = {
    "title": 3.0,
    "keywords": 2.0,
    "subjects": 1.5,
    "abstract": 1.0,
    "venue": 0.5,
}

# --- Metadata-reliability score per provider (NOT paper quality) -----------
SOURCE_SCORES: Dict[str, float] = {
    "OpenAlex": 92.0,
    "PubMed": 90.0,
    "Crossref": 88.0,
    "Semantic Scholar": 85.0,
    "arXiv": 82.0,
}

#: Citation score saturates at this count (log scale).
_CITATION_REFERENCE = 1000.0

#: Recency decay: score halves every N years (after the first year).
_RECENCY_HALF_LIFE = 7.0
_RECENCY_FLOOR = 15.0

_PREPRINT_HINTS = ("arxiv", "preprint", "biorxiv", "medrxiv", "ssrn", "research square")

_PEER_REVIEWED_TYPES = {
    "journal-article", "article", "proceedings-article", "book-chapter",
    "review", "review-article", "journalarticle", "conference",
}


@dataclass
class _Document:
    """Pre-computed BM25 representation of one paper."""

    token_weights: Dict[str, float]
    length: float
    title_text: str
    abstract_text: str


def _build_document(paper: Paper) -> _Document:
    token_weights: Dict[str, float] = {}

    def add(text: str, weight: float) -> None:
        for token in set(significance_tokens(text or "")):
            token_weights[token] = token_weights.get(token, 0.0) + weight

    add(paper.title, _FIELD_WEIGHTS["title"])
    add(" ".join(paper.keywords), _FIELD_WEIGHTS["keywords"])
    add(" ".join(paper.subjects), _FIELD_WEIGHTS["subjects"])
    add(paper.abstract, _FIELD_WEIGHTS["abstract"])
    add(paper.venue or "", _FIELD_WEIGHTS["venue"])

    return _Document(
        token_weights=token_weights,
        length=sum(token_weights.values()) or 1.0,
        title_text=normalize_title(paper.title),
        abstract_text=normalize_title(paper.abstract),
    )


def _query_term_weights(query_analysis: QueryAnalysis) -> Dict[str, float]:
    """Stemmed query terms with salience weights (expansions count less)."""
    weights: Dict[str, float] = {}
    explicit = {stem(term) for term in query_analysis.terms}
    for term in query_analysis.terms:
        weights[stem(term)] = 1.0
    for token in query_analysis.topical_terms:
        if token not in explicit:
            weights[token] = max(weights.get(token, 0.0), 0.6)
    return weights


def _bm25_scores(
    documents: Sequence[_Document],
    term_weights: Dict[str, float],
) -> List[float]:
    """Okapi BM25 over field-weighted pseudo-documents."""
    count = len(documents)
    if count == 0:
        return []

    document_frequency: Dict[str, int] = {}
    for document in documents:
        for term in term_weights:
            if term in document.token_weights:
                document_frequency[term] = document_frequency.get(term, 0) + 1

    average_length = sum(doc.length for doc in documents) / count or 1.0
    scores: List[float] = []

    for document in documents:
        score = 0.0
        for term, query_weight in term_weights.items():
            tf = document.token_weights.get(term, 0.0)
            if tf <= 0:
                continue
            df = document_frequency.get(term, 0)
            idf = math.log(1 + (count - df + 0.5) / (df + 0.5))
            denominator = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * document.length / average_length)
            score += query_weight * idf * (tf * (_BM25_K1 + 1)) / denominator
        scores.append(score)
    return scores


def _coverage(document: _Document, topical_terms: Set[str]) -> Tuple[float, List[str]]:
    """Fraction of query topic terms present, plus the matched term list."""
    if not topical_terms:
        return 0.0, []
    matched = sorted(term for term in topical_terms if term in document.token_weights)
    return len(matched) / len(topical_terms), matched


def _phrase_bonus(document: _Document, phrases: Sequence[str], query_analysis: QueryAnalysis) -> Tuple[float, Optional[str]]:
    """
    Reward exact phrase matches.

    Phrase evidence is the strongest signal that a paper is *about* the
    user's idea rather than merely mentioning its keywords.
    """
    bonus = 0.0
    evidence: Optional[str] = None

    full_query = query_analysis.normalized
    if full_query and len(full_query) > 12 and full_query in document.title_text:
        return 1.0, "title contains the full query phrase"

    for phrase in phrases:
        key = normalize_title(phrase)
        if len(key) < 8:
            continue
        if key in document.title_text:
            bonus += 0.20
            evidence = evidence or f"title contains “{phrase}”"
        elif key in document.abstract_text:
            bonus += 0.08
            evidence = evidence or f"abstract contains “{phrase}”"
    return min(bonus, 0.6), evidence


def compute_relevance(
    papers: Sequence[Paper],
    query_analysis: QueryAnalysis,
) -> Tuple[List[float], List[List[str]], Dict[int, str]]:
    """
    Return ``(relevance_scores 0-100, matched_terms per paper, evidence)``.

    Relevance is computed *relative to the best candidate in this pool*
    (100 = strongest match found for this query), which keeps the number
    meaningful for the user instead of an arbitrary absolute constant.
    """
    if not papers:
        return [], [], {}

    documents = [_build_document(paper) for paper in papers]
    term_weights = _query_term_weights(query_analysis)
    topical_terms = {stem(term) for term in query_analysis.topical_terms} or set(term_weights)

    bm25 = _bm25_scores(documents, term_weights)

    raw_scores: List[float] = []
    matched_terms: List[List[str]] = []
    evidence: Dict[int, str] = {}

    for position, document in enumerate(documents):
        coverage, matched = _coverage(document, topical_terms)
        phrase_bonus, phrase_evidence = _phrase_bonus(
            document, query_analysis.phrases, query_analysis
        )

        score = bm25[position]
        # Strong penalty when the paper matches none of the query's topics:
        # a single generic keyword must never float an unrelated paper up.
        if not matched:
            score *= 0.02
        else:
            score *= 0.7 + 0.3 * coverage
        score *= 1.0 + phrase_bonus

        raw_scores.append(score)
        matched_terms.append(matched)
        if phrase_evidence:
            evidence[position] = phrase_evidence
        else:
            evidence[position] = f"matched {len(matched)}/{len(topical_terms)} topic terms"

    best = max(raw_scores) if raw_scores else 0.0
    if best <= 0:
        return [0.0] * len(papers), matched_terms, evidence

    return [round(100.0 * score / best, 1) for score in raw_scores], matched_terms, evidence


def compute_quality(paper: Paper) -> Tuple[float, List[str]]:
    """
    Heuristic metadata-completeness score (0-100).

    This measures *how much is known about the paper*, not how good the
    research is -- the UI labels it accordingly.
    """
    score = 0.0
    reasons: List[str] = []

    abstract_length = len(paper.abstract or "")
    if abstract_length >= 800:
        score += 25
        reasons.append("detailed abstract")
    elif abstract_length >= 400:
        score += 18
        reasons.append("abstract available")
    elif abstract_length >= 120:
        score += 10
        reasons.append("short abstract")
    elif abstract_length > 0:
        score += 4
        reasons.append("minimal abstract")

    if paper.doi:
        score += 15
        reasons.append("DOI registered")

    venue = (paper.venue or "").lower()
    is_preprint = any(hint in venue for hint in _PREPRINT_HINTS)
    if venue and not is_preprint:
        score += 15
        reasons.append("published venue")
    elif venue:
        score += 8
        reasons.append("preprint server")

    doc_type = (paper.type or "").lower()
    if doc_type in _PEER_REVIEWED_TYPES:
        score += 15
        reasons.append(f"type: {paper.type}")
    elif doc_type:
        score += 6
        reasons.append(f"type: {paper.type}")

    if len(paper.sources) >= 3:
        score += 10
        reasons.append(f"corroborated by {len(paper.sources)} sources")
    elif len(paper.sources) == 2:
        score += 7
        reasons.append("found in 2 sources")

    if paper.keywords or paper.subjects:
        score += 5
        reasons.append("keywords/topics available")

    if len(paper.authors) >= 3:
        score += 15
        reasons.append(f"{len(paper.authors)} authors listed")
    elif paper.authors:
        score += 10
        reasons.append("author list available")

    return round(min(score, 100.0), 1), reasons


def compute_recency(paper: Paper, current_year: Optional[int] = None) -> Tuple[Optional[float], str]:
    """Exponentially decayed recency score (0-100), or ``None`` if year unknown."""
    if not paper.year:
        return None, "publication year not available in metadata"
    current_year = current_year or datetime.now(timezone.utc).year
    age = max(current_year - paper.year, 0)
    if age <= 1:
        score = 100.0
    else:
        score = max(_RECENCY_FLOOR, 100.0 * math.exp(-(age - 1) / _RECENCY_HALF_LIFE))
    return round(score, 1), f"published {paper.year} ({age} year{'s' if age != 1 else ''} old)"


def compute_citation(paper: Paper) -> Tuple[Optional[float], str]:
    """
    Log-scaled citation impact (0-100), saturating at 1000 citations.

    Returns ``None`` when no source reported a citation count -- ResearchOS
    never displays or scores invented citation numbers.
    """
    if paper.citation_count is None:
        return None, "citation count not available from the queried sources"
    count = max(paper.citation_count, 0)
    score = 100.0 * min(1.0, math.log1p(count) / math.log1p(_CITATION_REFERENCE))
    return round(score, 1), f"{count:,} citations (log scale, saturates at 1,000)"


def compute_source_score(paper: Paper) -> Tuple[float, str]:
    """Metadata-reliability score: the best-known source for this record."""
    scores = [SOURCE_SCORES[source] for source in paper.sources if source in SOURCE_SCORES]
    score = max(scores) if scores else (paper.source_score or 60.0)
    label = max(paper.sources, key=lambda s: SOURCE_SCORES.get(s, 0)) if paper.sources else paper.source
    return round(float(score), 1), f"indexed by {label}"


def combine_overall(
    components: Dict[str, Optional[float]],
    weights: RankingWeights,
) -> Tuple[float, Dict[str, float]]:
    """
    Weighted average over *available* components only.

    Returns ``(overall_score, effective_weights)``. When a component is
    unavailable (``None``) its weight is redistributed proportionally, so a
    paper without citation data is never implicitly punished.
    """
    weight_map = {
        "relevance": weights.relevance,
        "quality": weights.quality,
        "citation": weights.citation,
        "recency": weights.recency,
        "source": weights.source,
    }
    available = {
        name: score for name, score in components.items() if score is not None
    }
    total_weight = sum(weight_map[name] for name in available)
    if total_weight <= 0:
        return 0.0, {}

    effective = {name: weight_map[name] / total_weight for name in available}
    overall = sum(available[name] * effective[name] for name in available)
    return round(overall, 1), effective


def weighting_notes(weights: RankingWeights) -> List[str]:
    """Human-readable description of the ranking formula (shown in the UI)."""
    return [
        "Overall = "
        f"{weights.relevance:.2f}×relevance + {weights.quality:.2f}×quality + "
        f"{weights.citation:.2f}×citation impact + {weights.recency:.2f}×recency + "
        f"{weights.source:.2f}×source reliability",
        "Relevance uses BM25 over title/keywords/abstract/subjects plus "
        "topic-coverage and exact-phrase bonuses; it is scaled so the best "
        "candidate of the current result set scores 100.",
        "Weights are renormalised per paper when a component is unavailable "
        "(for example, sources that do not report citation counts).",
        "Quality is a metadata-completeness heuristic (DOI, venue, abstract, "
        "type, cross-source corroboration) — not a judgement of scientific merit.",
        "Source reliability reflects metadata openness/completeness of the "
        "provider (OpenAlex/PubMed/Crossref above preprints).",
    ]


def rank_papers(
    papers: Sequence[Paper],
    query_analysis: QueryAnalysis,
    weights: RankingWeights,
) -> List[Paper]:
    """Score every paper and return them sorted best-first with ranks set."""
    if not papers:
        return []

    relevance_scores, matched_terms, evidence = compute_relevance(papers, query_analysis)
    current_year = datetime.now(timezone.utc).year
    ranked: List[Paper] = []

    for position, paper in enumerate(papers):
        relevance = relevance_scores[position]
        quality, quality_reasons = compute_quality(paper)
        recency, recency_reason = compute_recency(paper, current_year)
        citation, citation_reason = compute_citation(paper)
        source_score, source_reason = compute_source_score(paper)

        overall, effective = combine_overall(
            {
                "relevance": relevance,
                "quality": quality,
                "citation": citation,
                "recency": recency,
                "source": source_score,
            },
            weights,
        )

        explanations = {
            "relevance": (
                f"Relevance {relevance:.0f}/100 — {evidence.get(position, '')}"
            ),
            "quality": (
                f"Quality {quality:.0f}/100 — "
                + (", ".join(quality_reasons) if quality_reasons else "limited metadata available")
            ),
            "recency": f"Recency {(recency if recency is not None else 0):.0f}/100 — {recency_reason}",
            "citation": (
                f"Citation impact {(citation if citation is not None else 0):.0f}/100 — {citation_reason}"
            ),
            "source": f"Source {source_score:.0f}/100 — {source_reason}",
            "overall": (
                f"Overall {overall:.0f}/100 — weighted over "
                + ", ".join(f"{name} {value:.2f}" for name, value in effective.items())
            ),
        }

        paper.relevance_score = relevance
        paper.quality_score = quality
        paper.recency_score = recency
        paper.citation_score = citation
        paper.source_score = source_score
        paper.overall_score = overall
        paper.score_explanations = explanations
        paper.matched_terms = matched_terms[position]
        ranked.append(paper)

    ranked.sort(
        key=lambda item: (
            -item.overall_score,
            -(item.citation_count if item.citation_count is not None else -1),
            -(item.year or 0),
            item.title,
        )
    )
    for index, paper in enumerate(ranked, start=1):
        paper.rank = index

    logger.info("Ranking complete — top score %.1f", ranked[0].overall_score if ranked else 0.0)
    return ranked
