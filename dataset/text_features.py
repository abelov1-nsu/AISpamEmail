import re
import numpy as np

# Признаки, не зависящие от длины и языка:
# - структурные (URL, CTA, HTML)
# - пунктуационные (caps, !, цифры)
# Perplexity и length НЕ используем — на этом датасете они ловят длину, а не AI.


URL_RE = re.compile(r"https?://\S+|www\.\S+")
HTML_RE = re.compile(r"<[a-zA-Z/][^>]*>")
EMAIL_RE = re.compile(r"\S+@\S+\.\S+")


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
    return int(bool(re.search(r"[$€₽£]\s?\d", text)))


def money_amounts(text: str) -> int:
    return len(re.findall(r"[$€₽£]\s?\d+", text))


def urgency_words(text: str) -> int:
    words = [
        "urgent", "immediately", "now", "today", "hurry",
        "expires", "limited", "last chance", "act now",
        "verify", "confirm", "suspend", "blocked",
    ]
    t = text.lower()
    return sum(1 for w in words if w in t)


def extract_features(subject: str, body: str, cta: str) -> dict:
    text = f"{subject} {body} {cta}"
    return {
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
    }