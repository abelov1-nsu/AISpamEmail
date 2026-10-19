"""Heuristic signals associated with AI-assisted writing."""
from ..constants import AI_LIKE_PHRASES
from ..schemas import Signal
from ..utils.text import clamp

class ExperimentalAIAnalyzer:
    """Calculate experimental, non-diagnostic AI-writing signals."""
    def analyze(self, text, style, repetition, cta):
        lower = text.lower()
        phrase_hits = [phrase for phrase in AI_LIKE_PHRASES if phrase in lower]
        average_length = style.get("average_sentence_length", 0.0)
        sentence_std = style.get("sentence_length_std", 0.0)
        regularity = clamp(1.0 - sentence_std / average_length) if average_length else 0.0
        lexical_diversity = style.get("lexical_diversity", 0.0)
        cta_count = cta.get("cta_count", 0)
        return [
            Signal("generic_ai_phrasing", clamp(len(phrase_hits) / 5), 0.7, f"Generic/formulaic phrases detected: {phrase_hits}"),
            Signal("sentence_regularity", regularity, 0.4, f"Sentence-length regularity score: {regularity:.2f}"),
            Signal("lexical_diversity", lexical_diversity, 0.1, f"Lexical diversity: {lexical_diversity:.2f}"),
            Signal("formulaic_cta", clamp(cta_count / 5), 0.5, f"Detected {cta_count} CTA phrases"),
        ]

__all__ = ["ExperimentalAIAnalyzer"]
