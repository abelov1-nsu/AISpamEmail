import re
import numpy as np


# ====================== РЕГУЛЯРКИ ======================
URL_RE = re.compile(r"https?://\S+|www\.\S+")
HTML_RE = re.compile(r"<[a-zA-Z/][^>]*>")
EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
MONEY_RE = re.compile(r"[$€₽£]\s?\d+")


# ====================== СТРУКТУРНЫЕ (12) ======================
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


# ====================== ТЕКСТОВЫЕ (5) ======================
def politeness_markers(text: str) -> int:
    markers = ["dear", "hello", "hi ", "best regards", "sincerely", "kind regards"]
    t = text.lower()
    return sum(1 for m in markers if m in t)


def ai_phrases(text: str) -> int:
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


# ====================== PARTIAL AI (3) ======================
def style_shift_score(text: str) -> float:
    """
    Насколько сильно меняется длина абзацев.
    Высокий score → часть текста AI, часть — человек.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 30]
    if len(paragraphs) < 2:
        return 0.0

    lengths = [len(p.split()) for p in paragraphs]
    avg = sum(lengths) / len(lengths)
    if avg == 0:
        return 0.0

    variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
    return (variance ** 0.5) / avg


def formality_shift(text: str) -> float:
    """
    Насколько разная формальность между абзацами.
    """
    formal_words = {"regarding", "furthermore", "therefore", "however", "moreover"}
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 30]
    if len(paragraphs) < 2:
        return 0.0

    scores = []
    for p in paragraphs:
        words = p.lower().split()
        if not words:
            continue
        scores.append(sum(1 for w in words if w in formal_words) / len(words))

    if len(scores) < 2:
        return 0.0

    return max(scores) - min(scores)


def human_typos(text: str) -> int:
    """
    Признаки ручного набора: двойные пробелы, 'i' вместо 'I',
    повторяющиеся буквы.
    """
    score = 0
    score += len(re.findall(r"\s{2,}", text))
    score += len(re.findall(r"\bi\b", text))
    score += len(re.findall(r"([a-z])\1{2,}", text))
    return score


# ====================== РЕГИОНАЛЬНЫЕ (7) ======================
def script_type(text: str) -> int:
    """
    0 = latin, 1 = cyrillic, 2 = mixed, 3 = other
    """
    has_latin = bool(re.search(r"[A-Za-z]", text))
    has_cyr = bool(re.search(r"[\u0400-\u04FF]", text))
    if has_latin and has_cyr:
        return 2
    if has_cyr:
        return 1
    if has_latin:
        return 0
    return 3


def currency_diversity(text: str) -> int:
    """Сколько разных валют в письме."""
    currencies = ["$", "€", "₽", "£", "¥", "₹", "₴", "₸"]
    return sum(1 for c in currencies if c in text)


def country_tld(text: str) -> int:
    """Есть ли URL с национальным TLD."""
    tlds = [".ru", ".de", ".cn", ".fr", ".uk", ".jp", ".br", ".in"]
    return sum(1 for t in tlds if t in text.lower())


def local_authority(text: str) -> int:
    """Упоминания локальных госорганов / брендов."""
    markers = [
        "фнс", "irs", "finanzamt", "hmrc", "cra", "ato",
        "сбербанк", "sberbank", "chase", "barclays", "deutsche bank",
        "пфр", "pension fund",
    ]
    t = text.lower()
    return sum(1 for m in markers if m in t)


def timezone_marker(text: str) -> int:
    """Часовые пояса."""
    markers = ["moscow time", "cet", "pst", "est", "gmt", "utc+", "msk"]
    t = text.lower()
    return sum(1 for m in markers if m in t)


def holiday_marker(text: str) -> int:
    """Праздники, к которым привязан спам."""
    markers = [
        "new year", "christmas", "lunar new year", "easter", "black friday",
        "новый год", "рождество", "8 марта", "23 февраля",
    ]
    t = text.lower()
    return sum(1 for m in markers if m in t)


def regional_keywords(text: str) -> int:
    """Локальные культурные/географические маркеры."""
    markers = [
        "moscow", "berlin", "beijing", "london", "paris", "tokyo",
        "москва", "берлин", "пекин", "лондон", "париж",
    ]
    t = text.lower()
    return sum(1 for m in markers if m in t)


# ====================== ГЛАВНАЯ ФУНКЦИЯ ======================
def extract_features(subject: str, body: str, cta: str) -> dict:
    """
    Извлекает 27 признаков из письма.
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

        # partial AI (3)
        "style_shift_score": style_shift_score(text),
        "formality_shift": formality_shift(text),
        "human_typos": human_typos(text),

        # региональные (7)
        "script_type": script_type(text),
        "currency_diversity": currency_diversity(text),
        "country_tld": country_tld(text),
        "local_authority": local_authority(text),
        "timezone_marker": timezone_marker(text),
        "holiday_marker": holiday_marker(text),
        "regional_keywords": regional_keywords(text),
    }
