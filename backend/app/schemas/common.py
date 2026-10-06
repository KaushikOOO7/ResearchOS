"""Shared response models (health, errors)."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Friendly error envelope -- never a raw stack trace."""

    status: str = "error"
    code: str = "error"
    message: str
    detail: Optional[str] = Field(
        default=None,
        description="Short, non-sensitive technical hint for developers.",
    )
    retryable: bool = False


class HealthResponse(BaseModel):
    """``GET /health`` payload."""

    status: str = "healthy"
    service: str = "ResearchOS"
    version: str
    environment: str
    gemini_configured: bool
    gemini_model: Optional[str] = None
    providers: Dict[str, bool] = Field(default_factory=dict)
    features: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
