"""Stylometric analysis of email text."""
import statistics
from collections import Counter
from ..utils.text import safe_mean, sentences, word_count, words

class StylometryAnalyzer:
    """Calculate lexical, sentence and punctuation statistics."""
    def analyze(self, text):
        token_list = words(text)
        sentence_list = sentences(text)
        if not token_list:
            return {"word_count": 0}
        sentence_lengths = [word_count(sentence) for sentence in sentence_list]
        unique_words = len(set(token_list))
        return {
            "word_count": len(token_list),
            "sentence_count": len(sentence_list),
            "unique_word_count": unique_words,
            "lexical_diversity": unique_words / len(token_list),
            "average_sentence_length": safe_mean(sentence_lengths),
            "sentence_length_std": statistics.stdev(sentence_lengths) if len(sentence_lengths) >= 2 else 0.0,
            "uppercase_ratio": sum(char.isupper() for char in text) / max(1, sum(char.isalpha() for char in text)),
            "digit_ratio": sum(char.isdigit() for char in text) / max(1, len(text)),
            "punctuation": dict(Counter(char for char in text if char in "!?;:,.-()")),
        }

__all__ = ["StylometryAnalyzer"]
