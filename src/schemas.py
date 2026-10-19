"""Typed data structures exchanged by analyzer components."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextPart:
    """A logical text fragment extracted from an email body."""

    part_id: str
    source: str
    text: str


@dataclass
class Signal:
    """One weighted evidence signal produced by an analyzer."""

    name: str
    value: float
    weight: float
    explanation: str

    @property
    def contribution(self) -> float:
        """Return the weighted contribution of this signal."""
        return self.value * self.weight


@dataclass
class AnalysisResult:
    """Aggregated result for one analyzed email."""

    email_id: str
    spam_score: float
    phishing_score: float
    ai_assisted_score: float
    judgement: str
    components: dict[str, Any] = field(default_factory=dict)
    signals: list[dict[str, Any]] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)
    ground_truth: str | None = None


__all__ = ["TextPart", "Signal", "AnalysisResult"]
