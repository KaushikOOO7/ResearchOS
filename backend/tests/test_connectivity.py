"""Connectivity preflight tests (no real network access)."""

from __future__ import annotations

import pytest
import requests

from app.utils import connectivity


@pytest.fixture(autouse=True)
def clear_cache():
    connectivity.reset_connectivity_cache()
    yield
    connectivity.reset_connectivity_cache()


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


def test_probe_reports_offline_when_egress_is_blocked(monkeypatch):
    def blocked(*args, **kwargs):
        raise requests.exceptions.SSLError("TLS handshake aborted")

    monkeypatch.setattr(connectivity.requests, "get", blocked)

    result = connectivity.get_connectivity(force=True)
    assert result["internet"] is False
    assert result["checked_host"] == connectivity.PROBE_HOST
    assert "SSLError" in result["detail"]


def test_probe_reports_online_on_success(monkeypatch):
    monkeypatch.setattr(connectivity.requests, "get", lambda *a, **k: _FakeResponse(200))

    result = connectivity.get_connectivity(force=True)
    assert result["internet"] is True
    assert result["detail"] == "HTTP 200"


def test_result_is_cached_between_calls(monkeypatch):
    calls = {"count": 0}

    def counting_get(*args, **kwargs):
        calls["count"] += 1
        return _FakeResponse(200)

    monkeypatch.setattr(connectivity.requests, "get", counting_get)

    first = connectivity.get_connectivity()
    second = connectivity.get_connectivity()

    assert calls["count"] == 1
    assert first["cached"] is False
    assert second["cached"] is True

    connectivity.get_connectivity(force=True)
    assert calls["count"] == 2
