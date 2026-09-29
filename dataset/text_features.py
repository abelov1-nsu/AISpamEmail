import re
import numpy as np


# ====================== РЕГУЛЯРКИ ======================
URL_RE = re.compile(r"https?://\S+|www\.\S+")
HTML_RE = re.compile(r"<[a-zA-Z/][^>]*>")
EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
MONEY_RE = re.compile(r"[$€₽£]\s?\d+")


# ====================== СТРУКТУРНЫЕ ПРИЗНАКИ ======================
def has_url(text: str) -> int:
    return int(bool(URL_RE.search(text)))


def url_count(text: str) -> int:
    return len(URL_RE.findall(text))


def has_email(text: str) -> int:
    return int(bool(EMAIL_RE.search(text)))


def has_html(text: str) -> int:
    return int(bool(HTML_RE.search(text)))


def has_cta(text: str, cta: str) -> int:
    return int(bool(str(cta).strip()))


def caps_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c.isupper()) / len(letters)


def exclamation_ratio(text: str) -> float:
    if not text:
        return 0.0
    return text.count("!") / len(text)


def question_ratio(text: str) -> float:
    if not text:
        return 0.0
    return text.count("?") / len(text)


def digit_ratio(text: str) -> float:
    if not text:
        return 0.0
    return sum(1 for c in text if c.isdigit()) / len(text)


def currency_present(text: str) -> int:
    return int(bool(MONEY_RE.search(text)))


def money_amounts(text: str) -> int:
    return len(MONEY_RE.findall(text))


def urgency_words(text: str) -> int:
    words = [
        "urgent", "immediately", "now", "today", "hurry",
        "expires", "limited", "last chance", "act now",
        "verify", "confirm", "suspend", "blocked",
    ]
    t = text.lower()
    return sum(1 for w in words if w in t)


# ====================== НОВЫЕ ТЕКСТОВЫЕ ПРИЗНАКИ ======================
def politeness_markers(text: str) -> int:
    """Dear / Hello / Best regards — типично для AI-писем."""
    markers = ["dear", "hello", "hi ", "best regards", "sincerely", "kind regards"]
    t = text.lower()
    return sum(1 for m in markers if m in t)


def ai_phrases(text: str) -> int:
    """Шаблонные AI-фразы."""
    phrases = [
        "i hope this email finds you well",
        "i am writing to",
        "please do not hesitate",
        "at your earliest convenience",
        "thank you for your attention",
        "we are pleased to inform",
        "kindly",
    ]
    t = text.lower()
    return sum(1 for p in phrases if p in t)


def avg_word_length(text: str) -> float:
    words = text.split()
    if not words:
        return 0.0
    return sum(len(w) for w in words) / len(words)


def sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?]+", text))


def avg_sentence_length(text: str) -> float:
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)


# ====================== ГЛАВНАЯ ФУНКЦИЯ ======================
def extract_features(subject: str, body: str, cta: str) -> dict:
    """
    Извлекает 17 признаков из письма.
    Не использует length и perplexity — чтобы не ловить длину и язык.
    """
    text = f"{subject} {body} {cta}"

    return {
        # структурные (12)
        "has_url": has_url(text),
        "url_count": url_count(text),
        "has_email": has_email(text),
        "has_html": has_html(text),
        "has_cta": has_cta(text, cta),
        "caps_ratio": caps_ratio(text),
        "exclamation_ratio": exclamation_ratio(text),
        "question_ratio": question_ratio(text),
        "digit_ratio": digit_ratio(text),
        "currency_present": currency_present(text),
        "money_amounts": money_amounts(text),
        "urgency_words": urgency_words(text),

        # текстовые (5)
        "politeness_markers": politeness_markers(text),
        "ai_phrases": ai_phrases(text),
        "avg_word_length": avg_word_length(text),
        "sentence_count": sentence_count(text),
        "avg_sentence_length": avg_sentence_length(text),
    }
