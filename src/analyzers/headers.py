"""Email header analysis."""

class HeaderAnalyzer:
    """Extract relevant delivery and authentication headers."""
    def analyze(self, headers):
        return {
            "from": headers.get("from"),
            "reply_to": headers.get("reply-to"),
            "return_path": headers.get("return-path"),
            "message_id": headers.get("message-id"),
            "authentication_results": headers.get("authentication-results"),
            "received_count": sum(1 for key in headers if key == "received"),
        }

__all__ = ["HeaderAnalyzer"]
