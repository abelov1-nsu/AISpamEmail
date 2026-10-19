"""Small, dependency-free helpers for text processing and scoring."""

from __future__ import annotations

import hashlib
import re
import statistics


def clamp(
    value: float,
    low: float = 0.0,
    high: float = 1.0,
) -> float:
    """Restrict ``value`` to the inclusive interval from ``low`` to ``high``."""
    return max(low, min(high, value))


def safe_mean(values: list[float]) -> float:
    """Return the arithmetic mean, or zero when the input is empty."""
    if not values:
        return 0.0

    return statistics.mean(values)


def sha256_text(text: str) -> str:
    """Return a SHA-256 digest for text using tolerant UTF-8 encoding."""
    encoded_text = text.encode("utf-8", errors="ignore")
    return hashlib.sha256(encoded_text).hexdigest()


def tokenize(text: str) -> list[str]:
    """Split text into lowercase word-like tokens."""
    return re.findall(r"\b[\w'-]+\b", text.lower())


def sentences(text: str) -> list[str]:
    """Split text on basic sentence boundaries and line breaks.

    This intentionally lightweight splitter is suitable for the current
    heuristic prototype. A language-aware tokenizer can replace it later.
    """
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def paragraphs(text: str) -> list[str]:
    """Split text into non-empty paragraphs separated by blank lines."""
    pieces = re.split(r"\n\s*\n", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def words(text: str) -> list[str]:
    """Return word tokens for ``text``.

    This named alias makes callers that work with word counts easier to read.
    """
    return tokenize(text)


def word_count(text: str) -> int:
    """Return the number of word-like tokens in ``text``."""
    return len(words(text))


def character_count(text: str) -> int:
    """Return the number of Unicode characters in ``text``."""
    return len(text)


__all__ = [
    "clamp",
    "safe_mean",
    "sha256_text",
    "tokenize",
    "sentences",
    "paragraphs",
    "words",
    "word_count",
    "character_count",
]
