"""
Google Gemini client for ResearchOS.

Handles the operational concerns of talking to a hosted LLM so the analysis
modules can stay focused on prompt + schema:

  * bounded exponential backoff (2s → 5s → 10s, with jitter)
  * retries only *transient* failures (429 / 500 / 502 / 503 / 504 / network)
  * never retries authentication or invalid-model errors
  * optional fallback model via ``GEMINI_FALLBACK_MODEL``
  * JSON response mode + friendly, non-leaking error messages

The API key is read from the environment and never logged.
"""

from __future__ import annotations

import os
import random
import socket
import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from app.config import settings
from app.utils.logging_setup import describe_secret, get_logger

logger = get_logger("gemini")

#: Base delays between retries (seconds). Attempt N uses index N.
RETRY_DELAYS: Tuple[float, ...] = (2.0, 5.0, 10.0)
MAX_RETRIES = 3
JITTER_MAX = 0.5

#: HTTP status codes worth retrying.
_TRANSIENT_CODES = {429, 500, 502, 503, 504}

#: Per-request timeout (milliseconds) for the Gemini SDK.
_REQUEST_TIMEOUT_MS = 120_000


class AIProviderError(RuntimeError):
    """
    Raised for every AI failure, carrying a *user-safe* message.

    ``code`` is a stable machine-readable identifier and ``retryable`` tells
    the API layer whether suggesting "try again" makes sense.
    """

    def __init__(
        self,
        message: str,
        code: str = "ai_error",
        retryable: bool = False,
        model: Optional[str] = None,
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.model = model


@dataclass
class GenerationResult:
    """A successful generation."""

    text: str
    model: str
    used_fallback: bool = False
    attempts: int = 1


def _load_sdk() -> Tuple[Any, Any, Any]:
    """Import the Google GenAI SDK lazily with a friendly error."""
    try:
        from google import genai  # type: ignore import-not-found
        from google.genai import errors, types  # type: ignore import-not-found

        return genai, types, errors
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise AIProviderError(
            "The AI analysis engine is not installed on the server "
            "(google-genai SDK missing).",
            code="sdk_missing",
        ) from exc


def _status_code(exc: Exception) -> Optional[int]:
    """Best-effort extraction of an HTTP status code from an SDK error."""
    for attribute in ("code", "status_code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    text = str(exc)
    for code in _TRANSIENT_CODES | {400, 401, 403, 404}:
        if str(code) in text:
            return code
    return None


def classify_error(exc: Exception) -> Tuple[bool, str, str]:
    """
    Map an SDK/network exception to ``(retryable, code, user_message)``.

    Messages are written for end users: no stack traces, no key material.
    """
    code = _status_code(exc)
    text = str(exc).upper()

    if code == 429 or "RESOURCE_EXHAUSTED" in text or "RATE LIMIT" in text or "QUOTA" in text:
        return (
            True,
            "rate_limited",
            "AI analysis is temporarily unavailable because the configured Gemini quota has "
            "been reached. Please try again later or configure another model/API quota.",
        )
    if code in {500, 502, 503, 504} or "UNAVAILABLE" in text or "DEADLINE_EXCEEDED" in text:
        return (
            True,
            "unavailable",
            "The AI service is temporarily unavailable. ResearchOS already retried with "
            "backoff and the fallback model — please try again shortly.",
        )
    if code in {401, 403} or "API_KEY_INVALID" in text or "PERMISSION_DENIED" in text:
        return (
            False,
            "auth_error",
            "AI analysis is unavailable because the configured GEMINI_API_KEY was rejected. "
            "Please check the server configuration.",
        )
    if code == 404 or "NOT_FOUND" in text:
        return (
            False,
            "model_not_found",
            "The configured AI model is not available for this API key. "
            "Set a valid GEMINI_MODEL on the server.",
        )
    if code == 400 or "INVALID_ARGUMENT" in text or "FAILED_PRECONDITION" in text:
        return (
            False,
            "bad_request",
            "The AI service rejected the request. This usually means the input was too long "
            "or malformed — try analysing a shorter paper.",
        )
    if (
        isinstance(exc, (ConnectionError, TimeoutError, socket.gaierror))
        or "CONNECT" in text
        or "TIMEOUT" in text
        or "NAME OR SERVICE NOT KNOWN" in text
        or "TEMPORARY FAILURE IN NAME RESOLUTION" in text
    ):
        return (
            True,
            "network",
            "Unable to connect to the AI service from the server (network or DNS failure). "
            "Please try again.",
        )
    return (
        False,
        "ai_error",
        "AI analysis failed unexpectedly. Please try again.",
    )


class GeminiClient:
    """Thin, resilient wrapper around ``client.models.generate_content``."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        max_retries: int = MAX_RETRIES,
    ):
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = (model or settings.gemini_model or "").strip()
        fallback = fallback_model if fallback_model is not None else settings.gemini_fallback_model
        self.fallback_model = (fallback or "").strip()
        self.max_retries = max(0, max_retries)
        self._client: Any = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        if not self.configured:
            raise AIProviderError(
                "AI analysis is unavailable because GEMINI_API_KEY is not configured on the "
                "server. Add it to backend/.env (or your host's environment variables) and "
                "restart the backend.",
                code="missing_api_key",
            )

        genai, types, _ = _load_sdk()
        logger.info("AI provider configured — key %s", describe_secret(self.api_key))

        http_options = None
        try:
            http_options = types.HttpOptions(timeout=_REQUEST_TIMEOUT_MS)
        except Exception:  # noqa: BLE001 - older SDKs may not accept timeout
            http_options = None

        try:
            self._client = genai.Client(api_key=self.api_key, http_options=http_options)
        except TypeError:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> GenerationResult:
        """
        Generate a JSON response, retrying transient failures.

        Tries ``GEMINI_MODEL`` first; if it is exhausted, tries
        ``GEMINI_FALLBACK_MODEL`` (when configured) before giving up.
        """
        client = self._get_client()
        _, types, _ = _load_sdk()

        models = [self.model] if self.model else []
        if self.fallback_model and self.fallback_model != self.model:
            models.append(self.fallback_model)
        if not models:
            raise AIProviderError(
                "No AI model is configured (GEMINI_MODEL is empty).",
                code="model_not_configured",
            )

        config_kwargs: dict = {
            "temperature": settings.gemini_temperature if temperature is None else temperature,
            "response_mime_type": "application/json",
            "max_output_tokens": settings.gemini_max_output_tokens,
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        last_error: Optional[Exception] = None
        last_message = "AI analysis failed unexpectedly. Please try again."
        last_code = "ai_error"
        retryable = False
        total_attempts = 0

        for model_index, model in enumerate(models):
            is_fallback = model_index > 0
            if is_fallback:
                logger.info("Falling back to model: %s", model)

            for attempt in range(self.max_retries + 1):
                total_attempts += 1
                try:
                    logger.info(
                        "AI analysis started (model=%s, attempt %d/%d)",
                        model,
                        attempt + 1,
                        self.max_retries + 1,
                    )
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(**config_kwargs),
                    )
                    text = self._extract_text(response, model)
                    logger.info("AI analysis completed (model=%s)", model)
                    return GenerationResult(
                        text=text,
                        model=model,
                        used_fallback=is_fallback,
                        attempts=total_attempts,
                    )
                except AIProviderError:
                    raise
                except Exception as exc:  # noqa: BLE001 - SDK raises many types
                    last_error = exc
                    retryable, last_code, last_message = classify_error(exc)
                    logger.info(
                        "AI request failed (%s): %s",
                        last_code,
                        str(exc)[:180].replace("\n", " "),
                    )

                    if not retryable:
                        raise AIProviderError(last_message, code=last_code, model=model) from exc
                    if attempt >= self.max_retries:
                        break

                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    delay += random.uniform(0, JITTER_MAX)
                    logger.info("Retrying in %.1fs", delay)
                    time.sleep(delay)

            if not is_fallback and len(models) > 1:
                logger.info("Primary model exhausted — trying fallback model")

        raise AIProviderError(last_message, code=last_code, retryable=retryable, model=models[-1]) from last_error

    @staticmethod
    def _extract_text(response: Any, model: str) -> str:
        """Pull text out of a response, failing loudly when it is empty."""
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        # Some responses carry parts-only payloads (e.g. safety-blocked text).
        candidates = []
        for candidate in getattr(response, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    candidates.append(part_text)
        joined = "\n".join(candidates).strip()
        if joined:
            return joined

        finish_reason = None
        for candidate in getattr(response, "candidates", None) or []:
            finish_reason = getattr(candidate, "finish_reason", None) or finish_reason
        raise AIProviderError(
            "The AI returned an empty response"
            + (f" (finish reason: {finish_reason})." if finish_reason else "."),
            code="empty_response",
            retryable=True,
            model=model,
        )


def gemini_configured() -> bool:
    """True when a Gemini API key is present (used by ``/health``)."""
    return bool(os.getenv("GEMINI_API_KEY") or settings.gemini_api_key)
