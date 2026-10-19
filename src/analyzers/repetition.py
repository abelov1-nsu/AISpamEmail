"""Repeated-word and template analysis."""
from collections import Counter
from ..utils.text import clamp, tokenize

class RepetitionAnalyzer:
    """Measure repeated words that may indicate templated content."""
    def analyze(self, text):
        tokens = tokenize(text)
        if not tokens:
            return {"repetition_score": 0.0}
        counts = Counter(tokens)
        repeated = {word: count for word, count in counts.items() if count >= 3}
        return {
            "unique_words": len(counts),
            "repeated_words": repeated,
            "repetition_score": clamp(sum(repeated.values()) / len(tokens)),
        }

__all__ = ["RepetitionAnalyzer"]
