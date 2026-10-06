"""
HTTP helpers shared by every research provider and the PDF downloader.

Provides:
  * a pooled :class:`requests.Session` with bounded retries for transient
    provider failures (429/5xx/connection resets),
  * typed provider errors so the search engine can isolate failures,
  * SSRF-safe URL validation before any outbound fetch.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import settings
from app.utils.logging_setup import get_logger

logger = get_logger("http")

USER_AGENT = (
    "ResearchOS/1.0 (academic research assistant; "
    f"mailto:{settings.contact_email or 'contact@example.com'})"
)


class ProviderError(RuntimeError):
    """Raised when an external research provider cannot be queried."""

    def __init__(self, provider: str, message: str, status_code: Optional[int] = None):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.status_code = status_code


class UnsafeUrlError(ValueError):
    """Raised when a URL fails validation (SSRF / non-http / unresolvable)."""


@dataclass
class FetchResult:
    ok: bool
    content: str = ""
    status_code: Optional[int] = None
    error: Optional[str] = None


def build_session(
    retries: int = 2,
    backoff: float = 0.6,
    status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504),
    pool_size: int = 16,
) -> requests.Session:
    """
    Create a ``requests.Session`` with retries for transient failures.

    Only idempotent GET requests are retried, and only for the transient
    status codes listed above -- authentication errors are never retried
    (they would just waste the provider's rate-limit budget).
    """
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        backoff_factor=backoff,
        status_forcelist=list(status_forcelist),
        allowed_methods=frozenset(["GET", "HEAD"]),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=pool_size,
        pool_maxsize=pool_size,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
        }
    )
    return session


# A module-level session reused by every provider (thread-safe for GETs).
_shared_session: Optional[requests.Session] = None


def get_session() -> requests.Session:
    """Return the shared provider session (created lazily)."""
    global _shared_session
    if _shared_session is None:
        _shared_session = build_session()
    return _shared_session


def get_json(
    provider: str,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
) -> Any:
    """
    GET ``url`` and decode JSON, raising :class:`ProviderError` on failure.

    Never logs request URLs that may embed credentials -- none of the
    ResearchOS providers use key-in-URL auth, but headers are used instead of
    query strings wherever a key is required.
    """
    timeout = timeout or settings.provider_timeout_seconds
    try:
        response = get_session().get(
            url,
            params=params,
            headers=headers,
            timeout=(min(timeout, 6.0), timeout),
        )
    except requests.exceptions.Timeout as exc:
        raise ProviderError(provider, f"request timed out after {timeout}s") from exc
    except requests.exceptions.RequestException as exc:
        raise ProviderError(provider, f"network error: {type(exc).__name__}") from exc

    if response.status_code >= 400:
        raise ProviderError(
            provider,
            f"HTTP {response.status_code}",
            status_code=response.status_code,
        )

    try:
        return response.json()
    except ValueError as exc:
        raise ProviderError(provider, "response was not valid JSON") from exc


def get_text(
    provider: str,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
) -> str:
    """GET ``url`` and return the response body as text."""
    timeout = timeout or settings.provider_timeout_seconds
    try:
        response = get_session().get(
            url,
            params=params,
            headers=headers,
            timeout=(min(timeout, 6.0), timeout),
        )
    except requests.exceptions.Timeout as exc:
        raise ProviderError(provider, f"request timed out after {timeout}s") from exc
    except requests.exceptions.RequestException as exc:
        raise ProviderError(provider, f"network error: {type(exc).__name__}") from exc

    if response.status_code >= 400:
        raise ProviderError(
            provider,
            f"HTTP {response.status_code}",
            status_code=response.status_code,
        )
    return response.text


# ---------------------------------------------------------------------------
# SSRF protection
# ---------------------------------------------------------------------------

_ALLOWED_SCHEMES = {"http", "https"}
_ALLOWED_PORTS = {None, 80, 443, 8080, 8443}


def _is_public_ip(ip_text: str) -> bool:
    """Return True only for globally routable unicast addresses."""
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (ip.version == 6 and ip.is_site_local)
    )


def validate_public_url(url: str, provider: str = "url") -> str:
    """
    Validate that ``url`` is safe to fetch server-side, then return it.

    Rejects: non-http(s) schemes, missing host, disallowed ports, and hosts
    that resolve to private / loopback / link-local / reserved addresses.
    This blocks the classic SSRF vectors (``localhost``, ``169.254.169.254``,
    ``10.x``, ``192.168.x``, ``::1``, ...) when downloading PDFs.

    Raises :class:`UnsafeUrlError` on failure.
    """
    if not isinstance(url, str) or not url.strip():
        raise UnsafeUrlError("URL is empty.")

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"Unsupported URL scheme: {parsed.scheme or 'none'}")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeUrlError("URL has no hostname.")

    try:
        port = parsed.port
    except ValueError as exc:  # invalid port in URL
        raise UnsafeUrlError("URL has an invalid port.") from exc
    if port not in _ALLOWED_PORTS:
        raise UnsafeUrlError(f"Port {port} is not allowed for downloads.")

    # Literal IP address?
    try:
        ipaddress.ip_address(hostname)
        if not _is_public_ip(hostname):
            raise UnsafeUrlError("URL points to a non-public IP address.")
        return url.strip()
    except ValueError:
        pass  # hostname is a domain name

    lowered = hostname.lower()
    if lowered in {"localhost", "localhost.localdomain"} or lowered.endswith(".local"):
        raise UnsafeUrlError("URL points to a local hostname.")

    try:
        infos = socket.getaddrinfo(hostname, port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Could not resolve hostname {hostname}.") from exc

    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise UnsafeUrlError(f"Could not resolve hostname {hostname}.")
    for address in addresses:
        if not _is_public_ip(address):
            raise UnsafeUrlError(
                f"Hostname {hostname} resolves to a non-public address."
            )
    return url.strip()


def hostname_of(url: str) -> str:
    """Return the lowercase hostname of ``url`` (empty string when invalid)."""
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
