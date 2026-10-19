"""Shared constants used by the heuristic email analyzers.

The values in this module are intentionally transparent and editable. They
are baseline vocabularies for the prototype, not a trained language model.
"""


# Minimum text length used by future short-message filtering.
MIN_TEXT_LENGTH = 20


# Common words reserved for future normalization and feature extraction.
COMMON_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "if",
    "then",
    "this",
    "that",
    "these",
    "those",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "have",
    "has",
    "had",
    "you",
    "your",
    "we",
    "our",
    "they",
    "their",
    "it",
    "as",
    "at",
    "by",
    "will",
    "can",
    "may",
}


# Formulaic phrases that may contribute to the experimental AI-writing score.
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


# Promotional and urgency phrases used by the spam analyzer.
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


# Call-to-action phrases used to detect formulaic user instructions.
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


__all__ = [
    "MIN_TEXT_LENGTH",
    "COMMON_WORDS",
    "AI_LIKE_PHRASES",
    "SPAM_PHRASES",
    "CTA_PHRASES",
]
