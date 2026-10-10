"""
Base Academic Provider Interface for ResearchOS.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.schemas.paper import Paper


class BaseProvider(ABC):
    """Abstract base class for all academic literature search providers."""

    def __init__(
        self,
        name: str,
        website: str,
        requires_auth: bool = False,
        default_enabled: bool = True,
    ):
        self.name = name
        self.website = website
        self.requires_auth = requires_auth
        self.is_enabled = default_enabled
        self.last_status = "Not tested"
        self.last_error: Optional[str] = None

    @abstractmethod
    def search(self, query: str, max_results: int = 25) -> List[Paper]:
        """Execute a search query against the provider's API."""
        pass

    def get_status_info(self) -> Dict[str, Any]:
        """Return provider capability and observed status."""
        return {
            "name": self.name,
            "website": self.website,
            "requires_auth": self.requires_auth,
            "is_enabled": self.is_enabled,
            "status": self.last_status,
            "last_error": self.last_error,
        }
