from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import statistics
import sys

from dataclasses import dataclass, field, asdict
from email import policy
from email.parser import BytesParser, Parser
from email.message import Message
from pathlib import Path
from collections import Counter
from typing import Any, Optional
from urllib.parse import urlparse


# ============================================================
# Configuration
# ============================================================

MIN_TEXT_LENGTH = 20

COMMON_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then",
    "this", "that", "these", "those", "to", "of", "in",
    "on", "for", "with", "from", "is", "are", "was",
    "were", "be", "been", "have", "has", "had",
    "you", "your", "we", "our", "they", "their",
    "it", "as", "at", "by", "will", "can", "may"
}

AI_LIKE_PHRASES = [
    "it's important to note",
    "it is important to note",
    "in conclusion",
    "in summary",
    "overall",
    "furthermore",
    "moreover",
    "additionally",
    "however",
    "therefore",
    "as mentioned above",
    "please note that",
    "it is worth noting",
    "i hope this message finds you well",
    "should you have any questions",
    "feel free to reach out",
    "don't hesitate to",
    "thank you for your understanding",
]

SPAM_PHRASES = [
    "act now",
    "limited time",
    "urgent",
    "immediately",
    "click here",
    "claim now",
    "exclusive offer",
    "you have been selected",
    "congratulations",
    "winner",
    "free",
    "risk free",
    "guaranteed",
    "special offer",
    "verify your account",
    "confirm your account",
    "suspended",
    "payment required",
    "last chance",
]

CTA_PHRASES = [
    "click here",
    "click now",
    "learn more",
    "verify",
    "confirm",
    "activate",
    "claim",
    "get started",
    "sign up",
    "register",
    "download",
    "open",
    "continue",
    "view",
    "access",
    "reset password",
]


# ============================================================
# Data structures
# ============================================================

@dataclass
class TextPart:
    part_id: str
    source: str
    text: str


@dataclass
class Signal:
    name: str
    value: float
    weight: float
    explanation: str

    @property
    def contribution(self) -> float:
        return self.value * self.weight


@dataclass
class AnalysisResult:
    email_id: str
    spam_score: float
    phishing_score: float
    ai_assisted_score: float

    judgement: str

    components: dict[str, Any] = field(default_factory=dict)
    signals: list[dict[str, Any]] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)

    ground_truth: Optional[str] = None


# ============================================================
# Generic utilities
# ============================================================

def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0

    return statistics.mean(values)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def tokenize(text: str) -> list[str]:
    return re.findall(r"\b[\w'-]+\b", text.lower())


def sentences(text: str) -> list[str]:
    """
    Very primitive sentence splitter.

    Later replace with:
        spaCy
        NLTK
        Stanza
        a transformer tokenizer
    """

    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)

    return [
        p.strip()
        for p in pieces
        if p.strip()
    ]


def paragraphs(text: str) -> list[str]:
    return [
        p.strip()
        for p in re.split(r"\n\s*\n", text)
        if p.strip()
    ]


def words(text: str) -> list[str]:
    return tokenize(text)


def word_count(text: str) -> int:
    return len(words(text))


def character_count(text: str) -> int:
    return len(text)


# ============================================================
# Email parsing
# ============================================================

class EmailParser:

    def parse_file(self, path: Path) -> dict[str, Any]:

        raw = path.read_bytes()

        message = BytesParser(
            policy=policy.default
        ).parsebytes(raw)

        return self.parse_message(message, path.name)

    def parse_message(
        self,
        message: Message,
        email_id: str
    ) -> dict[str, Any]:

        headers = {}

        for key, value in message.items():
            headers[key.lower()] = str(value)

        text_parts = []
        html_parts = []
        attachments = []

        if message.is_multipart():

            for index, part in enumerate(message.walk()):

                if part.is_multipart():
                    continue

                content_type = part.get_content_type()
                disposition = part.get_content_disposition()

                payload = part.get_payload(
                    decode=True
                )

                if payload is None:
                    continue

                filename = part.get_filename()

                if disposition == "attachment" or filename:

                    attachments.append({
                        "index": index,
                        "filename": filename,
                        "content_type": content_type,
                        "size": len(payload),
                    })

                elif content_type == "text/plain":

                    try:
                        text_parts.append(
                            payload.decode(
                                part.get_content_charset() or "utf-8",
                                errors="replace"
                            )
                        )
                    except Exception:
                        pass

                elif content_type == "text/html":

                    try:
                        html_parts.append(
                            payload.decode(
                                part.get_content_charset() or "utf-8",
                                errors="replace"
                            )
                        )
                    except Exception:
                        pass

        else:

            payload = message.get_payload(
                decode=True
            )

            if payload:

                text = payload.decode(
                    message.get_content_charset() or "utf-8",
                    errors="replace"
                )

                if message.get_content_type() == "text/html":
                    html_parts.append(text)
                else:
                    text_parts.append(text)

        return {
            "email_id": email_id,
            "headers": headers,
            "text": "\n\n".join(text_parts),
            "html": "\n\n".join(html_parts),
            "attachments": attachments,
        }


# ============================================================
# HTML analysis
# ============================================================

class HTMLAnalyzer:

    def analyze(self, html_text: str) -> dict[str, Any]:

        if not html_text:
            return {
                "present": False
            }

        links = re.findall(
            r'https?://[^\s"<>()]+',
            html_text,
            flags=re.IGNORECASE
        )

        tags = re.findall(
            r"<([a-zA-Z0-9]+)",
            html_text
        )

        tag_counter = Counter(
            tag.lower()
            for tag in tags
        )

        hidden_count = len(
            re.findall(
                r"display\s*:\s*none|visibility\s*:\s*hidden",
                html_text,
                flags=re.IGNORECASE
            )
        )

        script_count = len(
            re.findall(
                r"<script\b",
                html_text,
                flags=re.IGNORECASE
            )
        )

        iframe_count = len(
            re.findall(
                r"<iframe\b",
                html_text,
                flags=re.IGNORECASE
            )
        )

        button_count = len(
            re.findall(
                r"<button\b|<a[^>]+>",
                html_text,
                flags=re.IGNORECASE
            )
        )

        return {
            "present": True,
            "length": len(html_text),
            "tag_count": len(tags),
            "unique_tags": len(tag_counter),
            "top_tags": tag_counter.most_common(10),
            "url_count": len(links),
            "hidden_elements": hidden_count,
            "script_count": script_count,
            "iframe_count": iframe_count,
            "button_or_link_count": button_count,
        }


# ============================================================
# URL analysis
# ============================================================

class URLAnalyzer:

    URL_RE = re.compile(
        r"https?://[^\s<>\"]+",
        re.IGNORECASE
    )

    SUSPICIOUS_TLDS = {
        ".zip",
        ".top",
        ".click",
        ".work",
        ".download",
        ".xyz",
        ".tk",
        ".ml",
        ".ga",
        ".cf",
    }

    def extract(self, text: str) -> list[str]:

        return self.URL_RE.findall(text)

    def analyze_url(self, url: str) -> dict[str, Any]:

        try:
            parsed = urlparse(url)

            host = parsed.hostname or ""

            suspicious = 0.0
            reasons = []

            if "@" in parsed.netloc:
                suspicious += 0.4
                reasons.append("userinfo in URL")

            if len(url) > 150:
                suspicious += 0.2
                reasons.append("very long URL")

            if host.count(".") >= 4:
                suspicious += 0.15
                reasons.append("deep subdomain")

            if any(
                host.endswith(tld)
                for tld in self.SUSPICIOUS_TLDS
            ):
                suspicious += 0.25
                reasons.append("unusual TLD")

            if re.search(
                r"(login|verify|secure|account|password|update)",
                url,
                re.IGNORECASE
            ):
                suspicious += 0.15
                reasons.append("credential-related URL")

            return {
                "url": url,
                "host": host,
                "length": len(url),
                "suspicion": clamp(suspicious),
                "reasons": reasons,
            }

        except Exception as exc:

            return {
                "url": url,
                "suspicion": 0.5,
                "reasons": [
                    f"URL parsing failed: {exc}"
                ],
            }

    def analyze(self, text: str) -> dict[str, Any]:

        urls = self.extract(text)

        analyses = [
            self.analyze_url(url)
            for url in urls
        ]

        return {
            "count": len(urls),
            "urls": analyses,
            "average_suspicion": safe_mean([
                x["suspicion"]
                for x in analyses
            ]),
        }


# ============================================================
# Stylometric analysis
# ============================================================

class StylometryAnalyzer:

    def analyze(self, text: str) -> dict[str, Any]:

        token_list = words(text)
        sentence_list = sentences(text)

        if not token_list:
            return {
                "word_count": 0
            }

        sentence_lengths = [
            word_count(s)
            for s in sentence_list
        ]

        unique_words = len(set(token_list))

        lexical_diversity = (
            unique_words / len(token_list)
        )

        average_sentence_length = safe_mean(
            sentence_lengths
        )

        sentence_length_std = (
            statistics.stdev(sentence_lengths)
            if len(sentence_lengths) >= 2
            else 0.0
        )

        punctuation = Counter(
            char
            for char in text
            if char in "!?;:,.-()"
        )

        uppercase_ratio = (
            sum(1 for c in text if c.isupper())
            /
            max(
                1,
                sum(1 for c in text if c.isalpha())
            )
        )

        digit_ratio = (
            sum(1 for c in text if c.isdigit())
            /
            max(1, len(text))
        )

        return {
            "word_count": len(token_list),
            "sentence_count": len(sentence_list),
            "unique_word_count": unique_words,
            "lexical_diversity": lexical_diversity,
            "average_sentence_length": average_sentence_length,
            "sentence_length_std": sentence_length_std,
            "uppercase_ratio": uppercase_ratio,
            "digit_ratio": digit_ratio,
            "punctuation": dict(punctuation),
        }


# ============================================================
# Repetition / templating analysis
# ============================================================

class RepetitionAnalyzer:

    def analyze(self, text: str) -> dict[str, Any]:

        token_list = tokenize(text)

        if not token_list:
            return {
                "repetition_score": 0.0
            }

        counts = Counter(token_list)

        repeated = {
            word: count
            for word, count in counts.items()
            if count >= 3
        }

        repeated_tokens = sum(
            count
            for count in repeated.values()
        )

        repetition_score = (
            repeated_tokens / len(token_list)
        )

        return {
            "unique_words": len(counts),
            "repeated_words": repeated,
            "repetition_score": clamp(
                repetition_score
            ),
        }


# ============================================================
# CTA analysis
# ============================================================

class CTAAnalyzer:

    def analyze(self, text: str) -> dict[str, Any]:

        lower = text.lower()

        matches = []

        for phrase in CTA_PHRASES:

            count = lower.count(phrase)

            if count:
                matches.append({
                    "phrase": phrase,
                    "count": count
                })

        return {
            "cta_count": sum(
                item["count"]
                for item in matches
            ),
            "matches": matches,
        }


# ============================================================
# Spam analysis
# ============================================================

class SpamAnalyzer:

    def analyze(self, text: str) -> list[Signal]:

        lower = text.lower()

        signals = []

        spam_hits = []

        for phrase in SPAM_PHRASES:

            if phrase in lower:
                spam_hits.append(phrase)

        phrase_score = clamp(
            len(spam_hits) / 5
        )

        signals.append(
            Signal(
                name="spam_phrase_density",
                value=phrase_score,
                weight=1.0,
                explanation=(
                    f"Detected spam-oriented phrases: "
                    f"{spam_hits}"
                )
            )
        )

        exclamation_count = text.count("!")

        exclamation_score = clamp(
            exclamation_count / 10
        )

        signals.append(
            Signal(
                name="exclamation_density",
                value=exclamation_score,
                weight=0.4,
                explanation=(
                    f"{exclamation_count} exclamation marks"
                )
            )
        )

        uppercase_words = re.findall(
            r"\b[A-Z]{4,}\b",
            text
        )

        uppercase_score = clamp(
            len(uppercase_words) / 10
        )

        signals.append(
            Signal(
                name="uppercase_emphasis",
                value=uppercase_score,
                weight=0.5,
                explanation=(
                    f"{len(uppercase_words)} heavily "
                    f"capitalized words"
                )
            )
        )

        return signals


# ============================================================
# Phishing analysis
# ============================================================

class PhishingAnalyzer:

    def analyze(
        self,
        text: str,
        url_result: dict[str, Any]
    ) -> list[Signal]:

        lower = text.lower()

        signals = []

        credential_language = bool(
            re.search(
                r"(verify|confirm|login|password|"
                r"account|credential|security)",
                lower
            )
        )

        signals.append(
            Signal(
                name="credential_language",
                value=1.0 if credential_language else 0.0,
                weight=1.0,
                explanation=(
                    "Credential/account-related language "
                    "detected"
                    if credential_language
                    else
                    "No strong credential language detected"
                )
            )
        )

        url_score = url_result.get(
            "average_suspicion",
            0.0
        )

        signals.append(
            Signal(
                name="suspicious_urls",
                value=url_score,
                weight=1.5,
                explanation=(
                    f"Average URL suspicion: "
                    f"{url_score:.2f}"
                )
            )
        )

        return signals


# ============================================================
# Experimental AI-writing signals
# ============================================================

class ExperimentalAIAnalyzer:

    """
    IMPORTANT:

    This is intentionally NOT presented as a real AI detector.

    These are weak heuristic signals that allow us to experiment
    with the architecture before adding actual ML/API detectors.
    """

    def analyze(
        self,
        text: str,
        style: dict[str, Any],
        repetition: dict[str, Any],
        cta: dict[str, Any]
    ) -> list[Signal]:

        signals = []

        lower = text.lower()

        # ----------------------------------------------------
        # AI-like phrase usage
        # ----------------------------------------------------

        phrase_hits = [
            phrase
            for phrase in AI_LIKE_PHRASES
            if phrase in lower
        ]

        phrase_score = clamp(
            len(phrase_hits) / 5
        )

        signals.append(
            Signal(
                name="generic_ai_phrasing",
                value=phrase_score,
                weight=0.7,
                explanation=(
                    f"Generic/formulaic phrases detected: "
                    f"{phrase_hits}"
                )
            )
        )

        # ----------------------------------------------------
        # Sentence-length regularity
        # ----------------------------------------------------

        std = style.get(
            "sentence_length_std",
            0.0
        )

        avg = style.get(
            "average_sentence_length",
            0.0
        )

        if avg > 0:

            coefficient = std / avg

            regularity = clamp(
                1.0 - coefficient
            )

        else:

            regularity = 0.0

        signals.append(
            Signal(
                name="sentence_regularity",
                value=regularity,
                weight=0.4,
                explanation=(
                    f"Sentence-length regularity "
                    f"score: {regularity:.2f}"
                )
            )
        )

        # ----------------------------------------------------
        # Lexical diversity
        # ----------------------------------------------------

        diversity = style.get(
            "lexical_diversity",
            0.0
        )

        # This isn't inherently AI-like.
        # We merely expose it as a signal for later experiments.

        signals.append(
            Signal(
                name="lexical_diversity",
                value=diversity,
                weight=0.1,
                explanation=(
                    f"Lexical diversity: {diversity:.2f}"
                )
            )
        )

        # ----------------------------------------------------
        # CTA/formulaic behavior
        # ----------------------------------------------------

        cta_count = cta.get(
            "cta_count",
            0
        )

        cta_score = clamp(
            cta_count / 5
        )

        signals.append(
            Signal(
                name="formulaic_cta",
                value=cta_score,
                weight=0.5,
                explanation=(
                    f"Detected {cta_count} CTA phrases"
                )
            )
        )

        return signals


# ============================================================
# Header analysis
# ============================================================

class HeaderAnalyzer:

    def analyze(
        self,
        headers: dict[str, str]
    ) -> dict[str, Any]:

        result = {}

        result["from"] = headers.get(
            "from"
        )

        result["reply_to"] = headers.get(
            "reply-to"
        )

        result["return_path"] = headers.get(
            "return-path"
        )

        result["message_id"] = headers.get(
            "message-id"
        )

        result["authentication_results"] = headers.get(
            "authentication-results"
        )

        result["received_count"] = len(
            [
                key
                for key in headers
                if key == "received"
            ]
        )

        return result


# ============================================================
# Main analyzer
# ============================================================

class EmailAnalyzer:

    def __init__(self):

        self.html_analyzer = HTMLAnalyzer()
        self.url_analyzer = URLAnalyzer()
        self.style_analyzer = StylometryAnalyzer()
        self.repetition_analyzer = RepetitionAnalyzer()
        self.cta_analyzer = CTAAnalyzer()

        self.spam_analyzer = SpamAnalyzer()
        self.phishing_analyzer = PhishingAnalyzer()
        self.ai_analyzer = ExperimentalAIAnalyzer()

        self.header_analyzer = HeaderAnalyzer()

    # --------------------------------------------------------
    # Split email into logical components
    # --------------------------------------------------------

    def split_text(
        self,
        text: str
    ) -> list[TextPart]:

        parts = []

        paragraphs_list = paragraphs(text)

        for index, paragraph in enumerate(
            paragraphs_list
        ):

            parts.append(
                TextPart(
                    part_id=f"paragraph_{index}",
                    source="body",
                    text=paragraph
                )
            )

        return parts

    # --------------------------------------------------------
    # Analyze one email
    # --------------------------------------------------------

    def analyze(
        self,
        email: dict[str, Any]
    ) -> AnalysisResult:

        email_id = email["email_id"]

        text = email.get(
            "text",
            ""
        )

        html_text = email.get(
            "html",
            ""
        )

        headers = email.get(
            "headers",
            {}
        )

        # ----------------------------------------------------
        # Basic components
        # ----------------------------------------------------

        style = self.style_analyzer.analyze(
            text
        )

        repetition = self.repetition_analyzer.analyze(
            text
        )

        cta = self.cta_analyzer.analyze(
            text
        )

        urls = self.url_analyzer.analyze(
            text + "\n" + html_text
        )

        html_result = self.html_analyzer.analyze(
            html_text
        )

        header_result = self.header_analyzer.analyze(
            headers
        )

        # ----------------------------------------------------
        # Decision signals
        # ----------------------------------------------------

        spam_signals = self.spam_analyzer.analyze(
            text
        )

        phishing_signals = self.phishing_analyzer.analyze(
            text,
            urls
        )

        ai_signals = self.ai_analyzer.analyze(
            text,
            style,
            repetition,
            cta
        )

        # ----------------------------------------------------
        # Scores
        # ----------------------------------------------------

        spam_score = self.score_signals(
            spam_signals
        )

        phishing_score = self.score_signals(
            phishing_signals
        )

        ai_score = self.score_signals(
            ai_signals
        )

        # ----------------------------------------------------
        # Overall judgement
        # ----------------------------------------------------

        judgement = self.make_judgement(
            spam_score,
            phishing_score,
            ai_score
        )

        # ----------------------------------------------------
        # Convert signals to JSON-safe format
        # ----------------------------------------------------

        all_signals = (
            spam_signals
            + phishing_signals
            + ai_signals
        )

        signal_dicts = []

        for signal in all_signals:

            signal_dicts.append({
                "name": signal.name,
                "value": round(
                    signal.value,
                    4
                ),
                "weight": signal.weight,
                "contribution": round(
                    signal.contribution,
                    4
                ),
                "explanation": signal.explanation,
            })

        explanations = [
            signal.explanation
            for signal in all_signals
            if signal.value >= 0.5
        ]

        # ----------------------------------------------------
        # Component analysis
        # ----------------------------------------------------

        text_parts = self.split_text(
            text
        )

        component_results = []

        for part in text_parts:

            component_results.append({

                "id": part.part_id,

                "type": "text",

                "source": part.source,

                "length": len(part.text),

                "sha256": sha256_text(
                    part.text
                ),

                # Placeholder for future real detector
                "ai_analysis": {
                    "available": False,
                    "reason": (
                        "No actual AI detector "
                        "connected yet"
                    )
                }
            })

        return AnalysisResult(

            email_id=email_id,

            spam_score=round(
                spam_score,
                4
            ),

            phishing_score=round(
                phishing_score,
                4
            ),

            ai_assisted_score=round(
                ai_score,
                4
            ),

            judgement=judgement,

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

                "attachments": email.get(
                    "attachments",
                    []
                ),
            },

            signals=signal_dicts,

            explanations=explanations,
        )

    # --------------------------------------------------------
    # Weighted signal score
    # --------------------------------------------------------

    @staticmethod
    def score_signals(
        signals: list[Signal]
    ) -> float:

        if not signals:
            return 0.0

        numerator = sum(
            signal.value * signal.weight
            for signal in signals
        )

        denominator = sum(
            signal.weight
            for signal in signals
        )

        if denominator == 0:
            return 0.0

        return clamp(
            numerator / denominator
        )

    # --------------------------------------------------------
    # Final judgement
    # --------------------------------------------------------

    @staticmethod
    def make_judgement(
        spam_score: float,
        phishing_score: float,
        ai_score: float
    ) -> str:

        if phishing_score >= 0.75:
            return "likely_phishing"

        if spam_score >= 0.75:
            return "likely_spam"

        if ai_score >= 0.75:
            return "likely_ai_assisted"

        if (
            spam_score >= 0.45
            or phishing_score >= 0.45
            or ai_score >= 0.45
        ):
            return "suspicious"

        return "inconclusive"


# ============================================================
# Dataset loading
# ============================================================

class DatasetLoader:

    """
    Supports:

        directory/
            email1.eml
            email2.eml
            ...

    and later can easily support CSV/JSON datasets.
    """

    def load_directory(
        self,
        directory: Path
    ) -> list[Path]:

        return sorted(
            path
            for path in directory.rglob("*")
            if path.is_file()
            and path.suffix.lower() == ".eml"
        )

    def load_text_file(
        self,
        path: Path
    ) -> dict[str, Any]:

        text = path.read_text(
            encoding="utf-8",
            errors="replace"
        )

        return {
            "email_id": path.name,
            "headers": {},
            "text": text,
            "html": "",
            "attachments": [],
        }


# ============================================================
# Dataset evaluation
# ============================================================

class DatasetEvaluator:

    """
    Evaluates the prototype against ground truth.

    Expected labels:

        spam
        phishing
        legitimate
        ai_assisted

    This is deliberately simple.

    Later replace with sklearn metrics.
    """

    def evaluate(
        self,
        results: list[AnalysisResult],
        labels: dict[str, str]
    ) -> dict[str, Any]:

        rows = []

        for result in results:

            truth = labels.get(
                result.email_id
            )

            if truth is None:
                continue

            predicted = result.judgement

            rows.append({
                "id": result.email_id,
                "truth": truth,
                "prediction": predicted,
            })

        total = len(rows)

        correct = sum(
            1
            for row in rows
            if row["truth"] == row["prediction"]
        )

        accuracy = (
            correct / total
            if total
            else 0.0
        )

        confusion = {}

        for row in rows:

            key = (
                row["truth"],
                row["prediction"]
            )

            confusion[str(key)] = (
                confusion.get(
                    str(key),
                    0
                ) + 1
            )

        return {
            "samples": total,
            "correct": correct,
            "accuracy": accuracy,
            "confusion": confusion,
        }


# ============================================================
# Save JSON
# ============================================================

def save_json(
    data: Any,
    path: Path
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# Analyze dataset
# ============================================================

def analyze_dataset(
    input_directory: Path,
    output_directory: Path
):

    parser = EmailParser()
    analyzer = EmailAnalyzer()
    loader = DatasetLoader()

    files = loader.load_directory(
        input_directory
    )

    print(
        f"Found {len(files)} .eml files"
    )

    results = []

    for index, path in enumerate(files, 1):

        print(
            f"[{index}/{len(files)}] "
            f"{path.name}"
        )

        try:

            email = parser.parse_file(
                path
            )

            result = analyzer.analyze(
                email
            )

            results.append(result)

            output_path = (
                output_directory
                /
                f"{path.stem}.json"
            )

            save_json(
                asdict(result),
                output_path
            )

            print(
                f"    spam:       "
                f"{result.spam_score:.2f}"
            )

            print(
                f"    phishing:   "
                f"{result.phishing_score:.2f}"
            )

            print(
                f"    AI-assisted:"
                f" {result.ai_assisted_score:.2f}"
            )

            print(
                f"    judgement:  "
                f"{result.judgement}"
            )

        except Exception as exc:

            print(
                f"    ERROR: {exc}",
                file=sys.stderr
            )

    # --------------------------------------------------------
    # Dataset summary
    # --------------------------------------------------------

    summary = {

        "emails_analyzed": len(
            results
        ),

        "judgements": dict(
            Counter(
                result.judgement
                for result in results
            )
        ),

        "average_scores": {

            "spam": safe_mean([
                r.spam_score
                for r in results
            ]),

            "phishing": safe_mean([
                r.phishing_score
                for r in results
            ]),

            "ai_assisted": safe_mean([
                r.ai_assisted_score
                for r in results
            ]),
        }
    }

    save_json(
        summary,
        output_directory / "summary.json"
    )

    print()
    print("========== SUMMARY ==========")
    print(
        json.dumps(
            summary,
            indent=2
        )
    )


# ============================================================
# Synthetic test
# ============================================================

def run_demo():

    analyzer = EmailAnalyzer()

    examples = [

        {
            "email_id": "example_legitimate",

            "headers": {
                "from":
                    "professor@university.edu",
                "subject":
                    "Monday lecture materials"
            },

            "text": """
Hello everyone,

I've uploaded the lecture materials for Monday.
The slides cover the material we discussed last week.

Please let me know if anything is unclear.

Best,
Alex
""",

            "html": "",

            "attachments": []
        },

        {
            "email_id": "example_spam",

            "headers": {
                "from":
                    "unknown@example.xyz",
                "subject":
                    "URGENT!!!"
            },

            "text": """
URGENT!!!

Congratulations! You have been selected for an exclusive offer.

Click here immediately to claim your free reward.

This is your last chance. Act now!!!
""",

            "html": """
<a href="https://example.xyz/verify">
Click here
</a>
""",

            "attachments": []
        },

        {
            "email_id": "example_formulaic",

            "headers": {
                "from":
                    "notification@example.com"
            },

            "text": """
Hello,

I hope this message finds you well.

It is important to note that your account
requires verification.

Please click here to verify your account.

Should you have any questions,
feel free to reach out.

Thank you for your understanding.
""",

            "html": """
<html>
<body>
<a href="https://example.com/verify">
Verify your account
</a>
</body>
</html>
""",

            "attachments": []
        }
    ]

    for email in examples:

        result = analyzer.analyze(
            email
        )

        print()
        print(
            "=" * 70
        )

        print(
            json.dumps(
                asdict(result),
                indent=2,
                ensure_ascii=False
            )
        )


# ============================================================
# Command line interface
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Multi-signal email analyzer prototype"
        )
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        help=(
            "Directory containing .eml files"
        )
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("analysis_results"),
        help=(
            "Output directory for JSON results"
        )
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Run built-in synthetic examples"
        )
    )

    args = parser.parse_args()

    if args.demo:

        run_demo()
        return

    if args.dataset is None:

        print(
            "No dataset supplied. "
            "Use --demo or --dataset <directory>."
        )

        return

    analyze_dataset(
        args.dataset,
        args.output
    )


if __name__ == "__main__":
    main()