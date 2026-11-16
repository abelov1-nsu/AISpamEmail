"""Open WebUI configuration, transport and email-oriented AI tasks."""

from .config import settings
from .tasks import ai_judge, analyze_with_ai, segment_email
from .transport import OpenWebUIClient

__all__ = ["OpenWebUIClient", "analyze_with_ai", "ai_judge", "segment_email", "settings"]
