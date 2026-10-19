"""URL extraction and suspicion scoring."""
import re
from urllib.parse import urlparse
from ..utils.text import clamp, safe_mean

class URLAnalyzer:
    """Analyze URL structure and credential-related indicators."""
    URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
    SUSPICIOUS_TLDS = {".zip", ".top", ".click", ".work", ".download", ".xyz", ".tk", ".ml", ".ga", ".cf"}
    def extract(self, text):
        return self.URL_RE.findall(text)
    def analyze_url(self, url):
        try:
            parsed = urlparse(url)
            host = parsed.hostname or ""
            score = 0.0
            reasons = []
            checks = [("@" in parsed.netloc, .4, "userinfo in URL"), (len(url) > 150, .2, "very long URL"), (host.count(".") >= 4, .15, "deep subdomain"), (any(host.endswith(tld) for tld in self.SUSPICIOUS_TLDS), .25, "unusual TLD"), (bool(re.search(r"(login|verify|secure|account|password|update)", url, re.IGNORECASE)), .15, "credential-related URL")]
            for condition, value, reason in checks:
                if condition:
                    score += value
                    reasons.append(reason)
            return {"url": url, "host": host, "length": len(url), "suspicion": clamp(score), "reasons": reasons}
        except Exception as exc:
            return {"url": url, "suspicion": 0.5, "reasons": [f"URL parsing failed: {exc}"]}
    def analyze(self, text):
        analyses = [self.analyze_url(url) for url in self.extract(text)]
        return {"count": len(analyses), "urls": analyses, "average_suspicion": safe_mean([item["suspicion"] for item in analyses])}

__all__ = ["URLAnalyzer"]
