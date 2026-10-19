"""HTML structure analysis."""
import re
from collections import Counter

class HTMLAnalyzer:
    """Extract structural and potentially suspicious HTML indicators."""
    def analyze(self, html_text):
        if not html_text:
            return {"present": False}
        links = re.findall(r'https?://[^\s"<>()]+', html_text, flags=re.IGNORECASE)
        tags = re.findall(r"<([a-zA-Z0-9]+)", html_text)
        tag_counter = Counter(tag.lower() for tag in tags)
        return {
            "present": True,
            "length": len(html_text),
            "tag_count": len(tags),
            "unique_tags": len(tag_counter),
            "top_tags": tag_counter.most_common(10),
            "url_count": len(links),
            "hidden_elements": len(re.findall(r"display\s*:\s*none|visibility\s*:\s*hidden", html_text, flags=re.IGNORECASE)),
            "script_count": len(re.findall(r"<script\b", html_text, flags=re.IGNORECASE)),
            "iframe_count": len(re.findall(r"<iframe\b", html_text, flags=re.IGNORECASE)),
            "button_or_link_count": len(re.findall(r"<button\b|<a[^>]+>", html_text, flags=re.IGNORECASE)),
        }

__all__ = ["HTMLAnalyzer"]
