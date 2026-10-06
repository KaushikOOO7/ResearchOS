"""
Research provider abstraction.

Adding a new academic source = one new file that subclasses
:class:`ResearchSource` and is registered in
``app/research/search_engine.py``. Nothing else in the codebase changes.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.models.paper import Paper, QueryAnalysis
from app.research.normalizer import build_paper


@dataclass
class SourceOutcome:
    """Result of querying one provider (papers + telemetry)."""

    name: str
    papers: List[Paper] = field(default_factory=list)
    ok: bool = True
    elapsed_ms: int = 0
    error: Optional[str] = None
    configured: bool = True

    @property
    def result_count(self) -> int:
        return len(self.papers)


class ResearchSource(ABC):
    """
    Base class for every academic provider.

    Subclasses implement :meth:`fetch`. The base class handles timing,
    error isolation and normalisation, so a failing provider can never take
    the whole search down.
    """

    #: Human-readable source name shown on paper cards.
    name: str = "unknown"

    #: Metadata-reliability tier (1 = curated/open metadata, 2 = aggregator,
    #: 3 = preprint server). Used for the *source* ranking component only.
    tier: int = 2

    #: 0-100 "source reliability for metadata" score (NOT paper quality).
    source_score: float = 70.0

    def is_configured(self) -> bool:
        """False when the provider needs an API key that is not set."""
        return True

    def is_applicable(self, query_analysis: QueryAnalysis) -> bool:
        """False when the provider only covers a domain this query is not in."""
        return True

    @abstractmethod
    def fetch(self, query: str, limit: int, query_analysis: QueryAnalysis) -> List[Paper]:
        """Return up to ``limit`` normalised papers for ``query``."""

    # ------------------------------------------------------------------
    # Orchestration wrapper -- do not override
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int, query_analysis: QueryAnalysis) -> SourceOutcome:
        """Query the provider, capturing timings and isolating failures."""
        outcome = SourceOutcome(name=self.name, configured=self.is_configured())

        if not self.is_configured():
            outcome.ok = True
            outcome.error = "not configured"
            return outcome

        if not self.is_applicable(query_analysis):
            outcome.ok = True
            outcome.error = "not applicable to this query"
            return outcome

        started = time.perf_counter()
        try:
            papers = self.fetch(query, limit, query_analysis) or []
            outcome.papers = [p for p in papers if p.title][:limit]
            outcome.ok = True
        except Exception as exc:  # noqa: BLE001 - deliberate isolation boundary
            outcome.ok = False
            outcome.error = self._safe_error(exc)
            outcome.papers = []
        finally:
            outcome.elapsed_ms = int((time.perf_counter() - started) * 1000)

        return outcome

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        """Short, non-sensitive error description for the UI/telemetry."""
        message = str(exc)
        if len(message) > 220:
            message = message[:220] + "…"
        return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


# ---------------------------------------------------------------------------
# Normalisation
#
# The canonical paper builder lives in ``app/research/normalizer.py`` and is
# re-exported here so providers keep a single, short import path.
# ---------------------------------------------------------------------------

__all__ = ["ResearchSource", "SourceOutcome", "build_paper"]
