"""
ResearchOS configuration.

All runtime configuration is read from environment variables (see
``backend/.env.example``). Secrets are NEVER hardcoded and never logged.

The settings object is intentionally dependency-light (stdlib + python-dotenv)
so it can be imported from anywhere in the backend without side effects.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load backend/.env (does not override variables already set in the shell)
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent  # -> backend/
load_dotenv(BASE_DIR / ".env")
load_dotenv()  # also allow a project-root level .env


def _env(name: str, default: str = "") -> str:
    """Return a stripped environment variable (empty string when unset)."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_list(name: str, default: List[str]) -> List[str]:
    raw = _env(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class RankingWeights:
    """
    Configurable weights for the ResearchOS ranking pipeline.

    Weights are normalised at scoring time over the score components that are
    actually *available* for a paper (e.g. a paper without citation data is
    never penalised -- the remaining weights are renormalised instead).
    """

    relevance: float = 0.50
    quality: float = 0.20
    citation: float = 0.15
    recency: float = 0.10
    source: float = 0.05

    def as_dict(self) -> dict:
        return {
            "relevance": self.relevance,
            "quality": self.quality,
            "citation": self.citation,
            "recency": self.recency,
            "source": self.source,
        }


@dataclass(frozen=True)
class Settings:
    # --- AI provider -------------------------------------------------------
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    gemini_model: str = field(
        default_factory=lambda: _env("GEMINI_MODEL", "gemini-3.8-flash")
    )
    gemini_fallback_model: str = field(
        default_factory=lambda: _env("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")
    )
    gemini_max_output_tokens: int = field(
        default_factory=lambda: _env_int("GEMINI_MAX_OUTPUT_TOKENS", 8192)
    )
    gemini_temperature: float = field(
        default_factory=lambda: _env_float("GEMINI_TEMPERATURE", 0.2)
    )

    # --- Research providers (all optional except arXiv/OpenAlex/Crossref) ---
    openalex_email: str = field(default_factory=lambda: _env("OPENALEX_EMAIL"))
    crossref_email: str = field(default_factory=lambda: _env("CROSSREF_EMAIL"))
    semantic_scholar_api_key: str = field(
        default_factory=lambda: _env("SEMANTIC_SCHOLAR_API_KEY")
    )
    ncbi_api_key: str = field(default_factory=lambda: _env("NCBI_API_KEY"))
    pubmed_email: str = field(
        default_factory=lambda: _env("PUBMED_EMAIL") or _env("CROSSREF_EMAIL")
    )
    contact_email: str = field(
        default_factory=lambda: _env("CONTACT_EMAIL")
        or _env("OPENALEX_EMAIL")
        or _env("CROSSREF_EMAIL")
    )
    # Enables the PubMed source in addition to the general-purpose sources.
    pubmed_enabled: bool = field(
        default_factory=lambda: _env_bool("PUBMED_ENABLED", True)
    )

    # --- Search behaviour --------------------------------------------------
    target_candidates: int = field(
        default_factory=lambda: _env_int("RESEARCH_TARGET_CANDIDATES", 90)
    )
    max_results: int = field(default_factory=lambda: _env_int("RESEARCH_MAX_RESULTS", 30))
    min_results: int = field(default_factory=lambda: _env_int("RESEARCH_MIN_RESULTS", 30))
    provider_timeout_seconds: float = field(
        default_factory=lambda: _env_float("PROVIDER_TIMEOUT_SECONDS", 25.0)
    )
    # Hard wall-clock budget for the whole multi-source retrieval step.
    search_deadline_seconds: float = field(
        default_factory=lambda: _env_float("SEARCH_DEADLINE_SECONDS", 45.0)
    )

    # --- Ranking weights ---------------------------------------------------
    weights: RankingWeights = field(
        default_factory=lambda: RankingWeights(
            relevance=_env_float("RANK_WEIGHT_RELEVANCE", 0.50),
            quality=_env_float("RANK_WEIGHT_QUALITY", 0.20),
            citation=_env_float("RANK_WEIGHT_CITATION", 0.15),
            recency=_env_float("RANK_WEIGHT_RECENCY", 0.10),
            source=_env_float("RANK_WEIGHT_SOURCE", 0.05),
        )
    )

    # --- PDF / analysis limits --------------------------------------------
    pdf_max_bytes: int = field(
        default_factory=lambda: _env_int("PDF_MAX_BYTES", 25 * 1024 * 1024)
    )
    pdf_max_pages: int = field(default_factory=lambda: _env_int("PDF_MAX_PAGES", 80))
    pdf_download_timeout: float = field(
        default_factory=lambda: _env_float("PDF_DOWNLOAD_TIMEOUT", 45.0)
    )
    analysis_max_chars: int = field(
        default_factory=lambda: _env_int("ANALYSIS_MAX_CHARS", 120_000)
    )

    # --- API / CORS --------------------------------------------------------
    cors_origins: List[str] = field(
        default_factory=lambda: _env_list(
            "CORS_ORIGINS",
            [
                "http://localhost:5173",
                "http://localhost:5174",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:5174",
            ],
        )
    )
    # Regex for additional trusted origins (e.g. ephemeral preview domains).
    # Default covers the sandbox/preview hosts used during development.
    cors_origin_regex: str = field(
        default_factory=lambda: _env(
            "CORS_ORIGIN_REGEX", r"^https://([a-z0-9-]+\.)*(e2b\.app|arena\.ai)$"
        )
    )
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
    environment: str = field(default_factory=lambda: _env("ENVIRONMENT", "development"))

    # --- Derived -----------------------------------------------------------
    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

    def public_summary(self) -> dict:
        """
        A safe, secret-free view of the configuration for ``/health``.

        Only booleans / non-sensitive identifiers are exposed so the frontend
        can tell the user which capabilities are active.
        """
        return {
            "environment": self.environment,
            "gemini_configured": self.gemini_configured,
            "gemini_model": self.gemini_model,
            "gemini_fallback_model": self.gemini_fallback_model or None,
            "providers": {
                "arxiv": True,
                "openalex": True,
                "crossref": True,
                "semantic_scholar": bool(self.semantic_scholar_api_key),
                "pubmed": self.pubmed_enabled,
            },
            "contact_email_configured": bool(self.contact_email),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()


settings = get_settings()
