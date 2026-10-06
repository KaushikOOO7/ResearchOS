"""
Pydantic models for the ResearchOS AI paper analysis.

Two responsibilities:
  1. Describe the request/response contract of ``POST /analyze-paper``.
  2. Defensively normalise whatever the LLM returns into that exact
     structure, so a slightly malformed model response degrades gracefully
     instead of breaking the UI.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

NOT_STATED = "Not stated in the provided paper."

_PLACEHOLDERS = {
    "", "-", "n/a", "na", "none", "null", "not available", "not applicable",
    "unknown", "no information", "not mentioned", "not specified",
    "not stated in the provided paper.",
}


def _clean_item(value: Any) -> str:
    """Normalise one bullet: strip markdown markers, collapse spaces."""
    if value is None:
        return ""
    if isinstance(value, dict):
        # Models occasionally emit {"limitation": "..."} objects.
        parts = []
        for key, item in value.items():
            if isinstance(item, (str, int, float)) and str(item).strip():
                label = str(key).replace("_", " ").strip()
                parts.append(f"{label.capitalize()}: {item}" if label else str(item))
        value = " ".join(parts)
    text = str(value).strip()
    # Strip Markdown emphasis first: otherwise the leading "**" of a bold
    # prefix is consumed as a bullet marker and leaves a dangling "**".
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^\s*(?:[-*•‣–—]+|\d+[.)])\s*", "", text)
    text = text.strip("*_ ")
    text = " ".join(text.split())
    if text.lower() in _PLACEHOLDERS:
        return ""
    return text


def _clean_items(value: Any, limit: int = 12) -> List[str]:
    """Normalise a bullet list, dropping empty/placeholder entries."""
    if value is None:
        return []
    if isinstance(value, str):
        # Split on newlines / bullet markers when the model returns prose.
        pieces = re.split(r"\n+|(?<=[.;])\s+(?=[A-Z])", value)
        value = pieces if len(pieces) > 1 else [value]
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        value = [value]

    items: List[str] = []
    for entry in value:
        cleaned = _clean_item(entry)
        if cleaned:
            items.append(cleaned)
    return items[:limit]


def _clean_text(value: Any) -> str:
    """Normalise a paragraph field."""
    if value is None:
        return NOT_STATED
    if isinstance(value, (list, tuple)):
        value = " ".join(str(v) for v in value)
    text = str(value).strip()
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = " ".join(text.split())
    if text.lower() in _PLACEHOLDERS:
        return NOT_STATED
    return text


class ResearchGap(BaseModel):
    """Author-stated vs AI-inferred research gaps."""

    author_stated_gaps: List[str] = Field(default_factory=list)
    ai_inferred_gaps: List[str] = Field(default_factory=list)

    @field_validator("author_stated_gaps", "ai_inferred_gaps", mode="before")
    @classmethod
    def _normalise(cls, value: Any) -> List[str]:
        return _clean_items(value)


class PaperAnalysis(BaseModel):
    """The exact analysis structure ResearchOS promises the UI."""

    research_problem: str = NOT_STATED
    existing_approach: str = NOT_STATED
    proposed_method: str = NOT_STATED
    architecture: str = NOT_STATED
    dataset: str = NOT_STATED
    model_algorithm: str = NOT_STATED
    results: str = NOT_STATED

    limitations: List[str] = Field(default_factory=list)
    additional_technical_limitations: List[str] = Field(default_factory=list)
    why_approach_may_fail: List[str] = Field(default_factory=list)
    research_gap: ResearchGap = Field(default_factory=ResearchGap)
    possible_improvements: List[str] = Field(default_factory=list)
    new_research_direction: List[str] = Field(default_factory=list)
    overall_assessment: str = NOT_STATED

    @field_validator(
        "research_problem", "existing_approach", "proposed_method", "architecture",
        "dataset", "model_algorithm", "results", "overall_assessment", mode="before",
    )
    @classmethod
    def _normalise_text(cls, value: Any) -> str:
        return _clean_text(value)

    @field_validator(
        "limitations", "additional_technical_limitations", "why_approach_may_fail",
        "possible_improvements", "new_research_direction", mode="before",
    )
    @classmethod
    def _normalise_lists(cls, value: Any) -> List[str]:
        return _clean_items(value)

    @field_validator("research_gap", mode="before")
    @classmethod
    def _normalise_gap(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"ai_inferred_gaps": _clean_items(value)}
        return value

    def bullet_count(self) -> int:
        """Total number of bullet items (used for quick UI summaries)."""
        return (
            len(self.limitations)
            + len(self.additional_technical_limitations)
            + len(self.why_approach_may_fail)
            + len(self.research_gap.author_stated_gaps)
            + len(self.research_gap.ai_inferred_gaps)
            + len(self.possible_improvements)
            + len(self.new_research_direction)
        )


class PaperInput(BaseModel):
    """Paper reference sent by the frontend to the analysis endpoints."""

    title: str = Field(..., min_length=3, max_length=600)
    abstract: str = Field(default="", max_length=20_000)
    pdf_url: str = Field(default="", max_length=2_000)
    paper_url: str = Field(default="", max_length=2_000)
    doi: str = Field(default="", max_length=300)
    arxiv_id: str = Field(default="", max_length=100)
    source: str = Field(default="", max_length=80)
    year: Optional[int] = None
    authors: List[str] = Field(default_factory=list)
    paper_id: Optional[str] = Field(default="", max_length=64)

    @field_validator("title")
    @classmethod
    def _clean_title(cls, value: str) -> str:
        cleaned = " ".join((value or "").split())
        if len(cleaned) < 3:
            raise ValueError("Paper title is too short to analyse.")
        return cleaned


class AnalysisMetadata(BaseModel):
    """
    Provenance for an analysis: how much of the paper the model actually saw.

    This is what allows ResearchOS to be honest about coverage instead of
    pretending the model read the entire document.
    """

    model: Optional[str] = None
    used_fallback_model: bool = False
    pdf_url: Optional[str] = None
    pages: Optional[int] = None
    extracted_chars: Optional[int] = None
    analysed_chars: Optional[int] = None
    referenced_abstract_only: bool = False
    truncated: bool = False
    sections_detected: List[str] = Field(default_factory=list)
    elapsed_ms: int = 0
    warnings: List[str] = Field(default_factory=list)


class AnalyzePaperResponse(BaseModel):
    """Response for ``POST /analyze-paper``."""

    status: str = "success"
    paper_id: Optional[str] = None
    title: str
    analysis: PaperAnalysis
    metadata: AnalysisMetadata
