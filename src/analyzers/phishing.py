"""Heuristic phishing-signal analysis."""
import re
from ..schemas import Signal

class PhishingAnalyzer:
    """Detect credential language and suspicious-link evidence."""
    CREDENTIAL_PATTERN = re.compile(r"(verify|confirm|login|password|account|credential|security)")
    def analyze(self, text, url_result):
        credential_language = bool(self.CREDENTIAL_PATTERN.search(text.lower()))
        url_score = url_result.get("average_suspicion", 0.0)
        return [
            Signal("credential_language", 1.0 if credential_language else 0.0, 1.0, "Credential/account-related language detected" if credential_language else "No strong credential language detected"),
            Signal("suspicious_urls", url_score, 1.5, f"Average URL suspicion: {url_score:.2f}"),
        ]

__all__ = ["PhishingAnalyzer"]
