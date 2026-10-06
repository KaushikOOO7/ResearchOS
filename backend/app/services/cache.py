"""
Tiny in-process TTL cache.

Used to avoid re-querying every academic provider when a user re-runs the
same search (or navigates back to it). External calls are the expensive part
of ResearchOS, and the providers themselves ask clients to be polite.

This is intentionally simple: a process-local dictionary with expiry. When
the project gains PostgreSQL/Redis (roadmap Phase 7) this module is the only
thing that needs to change.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any, Optional


class TTLCache:
    """Thread-safe LRU + TTL cache for JSON-serialisable values."""

    def __init__(self, max_entries: int = 128, ttl_seconds: int = 900):
        self._store: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(*parts: Any) -> str:
        """Deterministic cache key from arbitrary JSON-serialisable parts."""
        payload = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                self.misses += 1
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                self._store.pop(key, None)
                self.misses += 1
                return None
            self._store.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        ttl = self._ttl if ttl_seconds is None else ttl_seconds
        with self._lock:
            self._store[key] = (time.monotonic() + ttl, value)
            self._store.move_to_end(key)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def stats(self) -> dict:
        with self._lock:
            return {
                "entries": len(self._store),
                "hits": self.hits,
                "misses": self.misses,
                "ttl_seconds": self._ttl,
            }


# Search results are cached for 15 minutes: academic metadata rarely changes
# faster than that, and it keeps repeated demos from hammering the providers.
search_cache = TTLCache(max_entries=128, ttl_seconds=900)
