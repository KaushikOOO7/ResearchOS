"""
ResearchOS logging.

Every backend log line is prefixed with ``[ResearchOS]`` so the pipeline is
easy to follow in a terminal:

    [ResearchOS] Search started
    [ResearchOS] Query: graph neural networks for drug discovery
    [ResearchOS] arXiv results: 40
    [ResearchOS] Candidates collected: 123
    [ResearchOS] Duplicates removed: 31
    [ResearchOS] Final Top 30 generated

Secrets are never logged: use :func:`describe_secret` when a key must be
referenced in a message.
"""

from __future__ import annotations

import logging

_ROOT_LOGGER_NAME = "researchos"
_CONFIGURED = False


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the root ``researchos`` logger (idempotent)."""
    global _CONFIGURED

    logger = logging.getLogger(_ROOT_LOGGER_NAME)
    if not _CONFIGURED:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[ResearchOS] %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
        _CONFIGURED = True

    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger, e.g. ``get_logger('search')``."""
    if name:
        return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
    return logging.getLogger(_ROOT_LOGGER_NAME)


def describe_secret(value: str | None) -> str:
    """
    Describe a secret without revealing it (``set (…abcd)`` / ``not set``).

    Only be used for provider keys, never for user content.
    """
    if not value:
        return "not set"
    tail = value[-4:] if len(value) >= 4 else "****"
    return f"set (…{tail})"
