"""Heuristic spam-signal analysis."""
import re
from ..constants import SPAM_PHRASES
from ..schemas import Signal
from ..utils.text import clamp

class SpamAnalyzer:
    """Detect promotional, urgent and visually emphatic spam signals."""
    def analyze(self, text):
        lower = text.lower()
        spam_hits = [phrase for phrase in SPAM_PHRASES if phrase in lower]
        uppercase_words = re.findall(r"\b[A-Z]{4,}\b", text)
        return [
            Signal("spam_phrase_density", clamp(len(spam_hits) / 5), 1.0, f"Detected spam-oriented phrases: {spam_hits}"),
            Signal("exclamation_density", clamp(text.count("!") / 10), 0.4, f"{text.count('!')} exclamation marks"),
            Signal("uppercase_emphasis", clamp(len(uppercase_words) / 10), 0.5, f"{len(uppercase_words)} heavily capitalized words"),
        ]

__all__ = ["SpamAnalyzer"]
