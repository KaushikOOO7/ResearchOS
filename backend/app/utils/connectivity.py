"""
Outbound connectivity preflight.

ResearchOS depends on external academic APIs. Hosted environments can block
that egress, and "no papers found" then looks like a product bug when it is
really a network policy. This module probes one lightweight endpoint and
reports the truth so ``/health`` (and therefore the UI) can say exactly what
is happening.

The probe result is cached briefly so ``/health`` stays fast and never becomes
a load generator against a provider.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

import requests

from app.utils.http import USER_AGENT
from app.utils.logging_setup import get_logger

logger = get_logger("connectivity")

#: A tiny OpenAlex request — the cheapest endpoint we depend on.
PROBE_URL = "https://api.openalex.org/works?per-page=1&select=id"
PROBE_HOST = "api.openalex.org"

_CACHE_TTL_SECONDS = 60.0
_PROBE_TIMEOUT = 4.0

_cache: Dict[str, Any] = {"checked_at": 0.0, "value": None}
_lock = threading.Lock()


def _probe() -> Dict[str, Any]:
    """Perform one real outbound request and describe the outcome."""
    started = time.perf_counter()
    try:
        response = requests.get(
            PROBE_URL,
            timeout=(3.0, _PROBE_TIMEOUT),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
    except requests.exceptions.Timeout as exc:
        detail = f"timed out after {_PROBE_TIMEOUT:.0f}s"
        code = type(exc).__name__
    except requests.exceptions.RequestException as exc:
        detail = "outbound HTTPS connection failed"
        code = type(exc).__name__
    else:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code < 500:
            return {
                "internet": True,
                "checked_host": PROBE_HOST,
                "detail": f"HTTP {response.status_code}",
                "elapsed_ms": elapsed_ms,
            }
        return {
            "internet": True,
            "checked_host": PROBE_HOST,
            "detail": f"{PROBE_HOST} responded HTTP {response.status_code}",
            "elapsed_ms": elapsed_ms,
        }

    logger.info("Connectivity probe failed: %s (%s)", detail, code)
    return {
        "internet": False,
        "checked_host": PROBE_HOST,
        "detail": f"{detail} ({code})",
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }


def get_connectivity(force: bool = False, ttl: float = _CACHE_TTL_SECONDS) -> Dict[str, Any]:
    """
    Return ``{internet, checked_host, detail, elapsed_ms, cached}``.

    Cached for ``ttl`` seconds; pass ``force=True`` to bypass the cache.
    """
    now = time.monotonic()
    with _lock:
        cached_value: Optional[Dict[str, Any]] = _cache["value"]
        age = now - _cache["checked_at"]
        if not force and cached_value is not None and age < ttl:
            return {**cached_value, "cached": True}

    result = _probe()

    with _lock:
        _cache["value"] = result
        _cache["checked_at"] = time.monotonic()

    return {**result, "cached": False}


def reset_connectivity_cache() -> None:
    """Clear the cached probe (used by tests)."""
    with _lock:
        _cache["value"] = None
        _cache["checked_at"] = 0.0
