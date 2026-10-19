"""General-purpose utilities used by the main analysis package."""

from .text import (
    character_count,
    clamp,
    paragraphs,
    safe_mean,
    sentences,
    sha256_text,
    tokenize,
    word_count,
    words,
)

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
