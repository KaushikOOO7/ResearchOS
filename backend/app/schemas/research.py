"""Pydantic request/response models for the research endpoints."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.paper import QueryAnalysis, SearchStats, SourceStatus


class ResearchRequest(BaseModel):
    """Body for ``POST /research``."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="The user's research idea or question.",
        examples=["Graph neural networks for drug discovery"],
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=50,
        description="Maximum number of ranked papers to return (default 30).",
    )
    sources: Optional[List[str]] = Field(
        default=None,
        description="Restrict the search to specific providers, e.g. ['arxiv','openalex'].",
    )
    year_from: Optional[int] = Field(
        default=None,
        ge=1900,
        le=2100,
        description="Optional minimum publication year filter.",
    )
    open_access_only: bool = Field(
        default=False,
        description="Only return papers with a directly accessible PDF.",
    )

    @field_validator("query")
    @classmethod
    def _clean_query(cls, value: str) -> str:
        cleaned = " ".join((value or "").split())
        if len(cleaned) < 3:
            raise ValueError("Query must contain at least 3 characters.")
        return cleaned


class ResearchResponse(BaseModel):
    """Response for ``POST /research``."""

    status: str = "success"
    message: Optional[str] = Field(
        default=None,
        description="Human-readable explanation when no papers were returned.",
    )
    query: str
    query_analysis: QueryAnalysis
    stats: SearchStats
    sources: List[SourceStatus] = Field(default_factory=list)
    weights: dict = Field(default_factory=dict)
    ranking_notes: List[str] = Field(default_factory=list)
    papers: List[dict] = Field(default_factory=list)


class PaperDetailResponse(BaseModel):
    """Response for ``GET /papers/{paper_id}``."""

    status: str = "success"
    paper: dict
