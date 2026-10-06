"""
PDF text cleaning and section detection.

``pypdf`` output is noisy: soft hyphens split words across line breaks,
ligatures break tokens, headers/footers repeat on every page, and the
reference list can be a third of the document. These helpers are deliberately
conservative heuristics -- they normalise text without ever rewriting
scientific content.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from app.utils.text import fix_ligatures, normalize_space

# --- Noise patterns --------------------------------------------------------

_PAGE_NUMBER_RE = re.compile(r"^\s*(?:page\s*)?\d{1,4}\s*$", re.IGNORECASE)
_ARXIV_STAMP_RE = re.compile(r"^\s*arXiv:\s*\S+\s*\[[^\]]*\]\s*.*$", re.IGNORECASE)
_JOURNAL_STAMP_RE = re.compile(
    r"^\s*(?:preprint|doi:|https?://doi\.org/|received:|accepted:|published:)\s*\S*\s*$",
    re.IGNORECASE,
)
_HYPHEN_BREAK_RE = re.compile(r"(\w+)-\s*\n\s*(\w+)")
_URL_LINE_RE = re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE)

# --- Section headings ------------------------------------------------------

_SECTION_ALIASES: Dict[str, List[str]] = {
    "abstract": ["abstract", "summary"],
    "introduction": ["introduction", "background", "motivation"],
    "related_work": [
        "related work", "literature review", "prior work", "background and related work",
        "related works", "previous work",
    ],
    "methodology": [
        "method", "methods", "methodology", "proposed method", "proposed approach",
        "our approach", "materials and methods", "system design", "framework",
        "model", "architecture", "proposed model", "proposed framework",
    ],
    "experiments": ["experiment", "experiments", "experimental setup", "evaluation",
                    "experimental settings", "datasets", "data", "evaluation setup"],
    "results": ["results", "results and discussion", "findings", "analysis"],
    "discussion": ["discussion", "limitations", "threats to validity"],
    "conclusion": ["conclusion", "conclusions", "conclusion and future work",
                   "conclusion and future directions"],
    "future_work": ["future work", "future directions", "future research",
                    "recommendations"],
    "references": ["references", "bibliography"],
}

_HEADING_RE = re.compile(
    r"^\s*(?:(?:[0-9]{1,2}|[IVXLC]{1,4})[.)]?\s+)?"
    r"(?P<title>[A-Z][A-Za-z /&-]{2,60}?)\s*$"
)


def clean_pdf_text(raw_text: str) -> str:
    """
    Normalise extracted PDF text.

    * fixes ligatures / typographic characters,
    * joins words split across line breaks (``distribu-\\nted`` -> ``distributed``),
    * removes page numbers, arXiv stamps and standalone URL lines,
    * collapses repeated whitespace.
    """
    if not raw_text:
        return ""

    text = fix_ligatures(raw_text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Join hyphenated line breaks before touching whitespace.
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)

    kept_lines: List[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            kept_lines.append("")
            continue
        if _PAGE_NUMBER_RE.match(stripped):
            continue
        if _ARXIV_STAMP_RE.match(stripped):
            continue
        if _JOURNAL_STAMP_RE.match(stripped):
            continue
        if _URL_LINE_RE.match(stripped):
            continue
        kept_lines.append(stripped)

    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def detect_sections(text: str) -> Tuple[Dict[str, str], List[str]]:
    """
    Best-effort section segmentation.

    Returns ``(sections, detected_names)``. Sections that cannot be found are
    simply absent from the mapping -- callers must not assume completeness.
    """
    if not text:
        return {}, []

    lines = text.split("\n")
    alias_lookup: Dict[str, str] = {}
    for canonical, aliases in _SECTION_ALIASES.items():
        for alias in aliases:
            alias_lookup[alias] = canonical

    headings: List[Tuple[int, str]] = []
    for index, line in enumerate(lines):
        if len(line) > 70:
            continue
        match = _HEADING_RE.match(line)
        if not match:
            continue
        candidate = match.group("title").strip().lower().rstrip(".:")
        candidate = re.sub(r"\s+", " ", candidate)
        canonical = alias_lookup.get(candidate)
        if canonical:
            headings.append((index, canonical))

    if not headings:
        return {}, []

    # Keep the first occurrence of each canonical section and drop headings
    # that appear after "references" (they are usually citations of titles).
    ordered: List[Tuple[int, str]] = []
    seen = set()
    for index, canonical in headings:
        if canonical in seen:
            continue
        if any(prev == "references" for _, prev in ordered):
            break
        seen.add(canonical)
        ordered.append((index, canonical))

    sections: Dict[str, str] = {}
    for position, (index, canonical) in enumerate(ordered):
        end = ordered[position + 1][0] if position + 1 < len(ordered) else len(lines)
        body = "\n".join(lines[index + 1: end]).strip()
        if body:
            sections[canonical] = body

    return sections, list(sections.keys())


def compose_analysis_text(
    paper_text: str,
    abstract: str,
    sections: Dict[str, str],
    max_chars: int,
) -> Tuple[str, bool]:
    """
    Build the text handed to the language model.

    When section detection succeeded we assemble a *section-labelled*
    document (cheaper for the model to ground on and easier to cite later);
    otherwise we fall back to the head of the cleaned full text.

    Returns ``(text, truncated)``.
    """
    from app.utils.text import truncate_smart

    if sections:
        # Order the sections the way a reader expects them.
        order = [
            "abstract", "introduction", "related_work", "methodology",
            "experiments", "results", "discussion", "conclusion",
            "future_work", "references",
        ]
        blocks: List[str] = []
        if abstract:
            blocks.append(f"## ABSTRACT\n{abstract}")
        for name in order:
            body = sections.get(name)
            if not body or name == "abstract":
                continue
            # References are rarely useful for analysis and are expensive
            # in tokens: keep a short tail only.
            if name == "references":
                body = body[:2000]
            blocks.append(f"## {name.upper().replace('_', ' ')}\n{body}")
        document = "\n\n".join(blocks)
        # If section segmentation captured far less content than the raw
        # text, the heading detector likely misfired: prefer the full text.
        too_short = len(document) < 0.6 * len(paper_text or "") and len(document) < 1500
        if not blocks or too_short:
            document = paper_text or document
    else:
        document = paper_text

    if len(document) > max_chars:
        return truncate_smart(document, max_chars), True
    return document, False


def page_snippet(page_text: str, limit: int = 240) -> str:
    """Short, single-line excerpt of a page (used for evidence hints)."""
    return normalize_space(page_text)[:limit]
