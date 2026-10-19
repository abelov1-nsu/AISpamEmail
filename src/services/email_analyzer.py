"""Orchestration service for analyzing one email message."""

from __future__ import annotations

from typing import Any

from ..analyzers.ai_assisted import ExperimentalAIAnalyzer
from ..analyzers.cta import CTAAnalyzer
from ..analyzers.headers import HeaderAnalyzer
from ..analyzers.html import HTMLAnalyzer
from ..analyzers.phishing import PhishingAnalyzer
from ..analyzers.repetition import RepetitionAnalyzer
from ..analyzers.spam import SpamAnalyzer
from ..analyzers.stylometry import StylometryAnalyzer
from ..analyzers.urls import URLAnalyzer
from ..schemas import AnalysisResult, Signal, TextPart
from ..utils.text import clamp, paragraphs, sha256_text, word_count


class EmailAnalyzer:
    """Combine individual analyzers into one explainable result."""

    def __init__(self) -> None:
        self.html_analyzer = HTMLAnalyzer()
        self.url_analyzer = URLAnalyzer()
        self.style_analyzer = StylometryAnalyzer()
        self.repetition_analyzer = RepetitionAnalyzer()
        self.cta_analyzer = CTAAnalyzer()
        self.spam_analyzer = SpamAnalyzer()
        self.phishing_analyzer = PhishingAnalyzer()
        self.ai_analyzer = ExperimentalAIAnalyzer()
        self.header_analyzer = HeaderAnalyzer()

    def split_text(self, text: str) -> list[TextPart]:
        """Split the body into paragraph-level text artifacts."""
        return [
            TextPart(
                part_id=f"paragraph_{index}",
                source="body",
                text=paragraph,
            )
            for index, paragraph in enumerate(paragraphs(text))
        ]

    def analyze(self, email: dict[str, Any]) -> AnalysisResult:
        """Analyze one parsed email and return scores plus explanations."""
        email_id = email["email_id"]
        text = email.get("text", "")
        html_text = email.get("html", "")
        headers = email.get("headers", {})

        style = self.style_analyzer.analyze(text)
        repetition = self.repetition_analyzer.analyze(text)
        cta = self.cta_analyzer.analyze(text)
        urls = self.url_analyzer.analyze(text + "\n" + html_text)
        html_result = self.html_analyzer.analyze(html_text)
        header_result = self.header_analyzer.analyze(headers)

        spam_signals = self.spam_analyzer.analyze(text)
        phishing_signals = self.phishing_analyzer.analyze(text, urls)
        ai_signals = self.ai_analyzer.analyze(text, style, repetition, cta)

        spam_score = self.score_signals(spam_signals)
        phishing_score = self.score_signals(phishing_signals)
        ai_score = self.score_signals(ai_signals)
        all_signals = spam_signals + phishing_signals + ai_signals

        signal_dicts = [
            {
                "name": signal.name,
                "value": round(signal.value, 4),
                "weight": signal.weight,
                "contribution": round(signal.contribution, 4),
                "explanation": signal.explanation,
            }
            for signal in all_signals
        ]

        component_results = [
            {
                "id": part.part_id,
                "type": "text",
                "source": part.source,
                "length": len(part.text),
                "sha256": sha256_text(part.text),
                "ai_analysis": {
                    "available": False,
                    "reason": "No actual AI detector connected yet",
                },
            }
            for part in self.split_text(text)
        ]

        return AnalysisResult(
            email_id=email_id,
            spam_score=round(spam_score, 4),
            phishing_score=round(phishing_score, 4),
            ai_assisted_score=round(ai_score, 4),
            judgement=self.make_judgement(
                spam_score,
                phishing_score,
                ai_score,
            ),
            components={
                "text": {
                    "length": len(text),
                    "word_count": word_count(text),
                    "parts": component_results,
                },
                "style": style,
                "repetition": repetition,
                "cta": cta,
                "urls": urls,
                "html": html_result,
                "headers": header_result,
                "attachments": email.get("attachments", []),
            },
            signals=signal_dicts,
            explanations=[
                signal.explanation
                for signal in all_signals
                if signal.value >= 0.5
            ],
        )

    @staticmethod
    def score_signals(signals: list[Signal]) -> float:
        """Return a weighted mean of signal values in the [0, 1] range."""
        if not signals:
            return 0.0

        total_weight = sum(signal.weight for signal in signals)
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(
            signal.value * signal.weight
            for signal in signals
        )
        return clamp(weighted_sum / total_weight)

    @staticmethod
    def make_judgement(
        spam_score: float,
        phishing_score: float,
        ai_score: float,
    ) -> str:
        """Convert component scores into the current prototype verdict."""
        if phishing_score >= 0.75:
            return "likely_phishing"
        if spam_score >= 0.75:
            return "likely_spam"
        if ai_score >= 0.75:
            return "likely_ai_assisted"
        if max(spam_score, phishing_score, ai_score) >= 0.45:
            return "suspicious"
        return "inconclusive"


__all__ = ["EmailAnalyzer"]
