"""Call-to-action phrase analysis."""
from ..constants import CTA_PHRASES

class CTAAnalyzer:
    """Find known call-to-action phrases in email text."""
    def analyze(self, text):
        lower_text = text.lower()
        matches = []
        for phrase in CTA_PHRASES:
            count = lower_text.count(phrase)
            if count:
                matches.append({"phrase": phrase, "count": count})
        return {"cta_count": sum(item["count"] for item in matches), "matches": matches}

__all__ = ["CTAAnalyzer"]
