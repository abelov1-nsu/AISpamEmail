import re

# ====================== МАРКЕРЫ ======================
GREETING_MARKERS = [
    # EN formal
    "dear", "to whom it may concern", "good morning", "good afternoon", "good evening",
    # EN informal
    "hello", "hi", "hey", "greetings", "what's up",
    # RU formal
    "здравствуйте", "добрый день", "добрый вечер", "доброе утро", "уважаемый", "уважаемая",
    # RU informal
    "привет", "приветствую", "здорово", "доброго времени суток",
]

CLOSING_MARKERS = [
    # EN formal
    "best regards", "kind regards", "warm regards", "sincerely", "respectfully",
    "yours truly", "yours faithfully", "looking forward to hearing",
    "thank you for your time", "thank you for your attention",
    # EN informal
    "thanks", "cheers", "talk soon", "catch you later", "take care", "have a great",
    # RU formal
    "с уважением", "с наилучшими пожеланиями", "искренне ваш", "искренне ваша",
    "заранее благодарю", "благодарю за внимание",
    # RU informal
    "спасибо", "всего доброго", "всего хорошего", "до связи", "до встречи",
    "хорошего дня", "берегите себя",
]

IMG_SRC_RE = re.compile(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', re.IGNORECASE)


# ====================== ВСПОМОГАТЕЛЬНЫЕ ======================
def extract_image_urls(text: str) -> list:
    """Ищет ссылки на картинки в HTML-коде письма."""
    return IMG_SRC_RE.findall(text)


def split_sentences(text: str) -> list:
    """Разбивает текст на предложения (учитывает . ! ? …)."""
    text = re.sub(r"\s+", " ", str(text).strip())
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


# ====================== ПАРСЕР ======================
def parse_email_structure(text: str) -> dict:
    """
    Делит текст на: greeting, body, closing, images.
    Работает с EN и RU, формальным и неформальным стилем.
    """
    # 1. Ищем картинки
    images = extract_image_urls(text)

    # 2. Убираем HTML-теги картинок, чтобы не мешали парсить текст
    text_clean = IMG_SRC_RE.sub(' ', text)

    sentences = split_sentences(text_clean)

    if len(sentences) == 0:
        return {"greeting": "", "body": "", "closing": "", "images": images}

    if len(sentences) == 1:
        return {"greeting": sentences[0], "body": "", "closing": "", "images": images}

    if len(sentences) == 2:
        return {"greeting": sentences[0], "body": sentences[1], "closing": "", "images": images}

    # --- Концовка ---
    closing = ""
    for i in range(len(sentences) - 1, max(len(sentences) - 4, 0) - 1, -1):
        sent_lower = sentences[i].lower()
        if any(marker in sent_lower for marker in CLOSING_MARKERS):
            closing = " ".join(sentences[i:])
            sentences = sentences[:i]
            break

    if not closing and len(sentences) > 4:
        closing = sentences[-1]
        sentences = sentences[:-1]

    # --- Приветствие ---
    greeting = ""
    for i in range(min(2, len(sentences))):
        sent_lower = sentences[i].lower()
        if any(marker in sent_lower[:40] for marker in GREETING_MARKERS):
            greeting = " ".join(sentences[:i + 1])
            sentences = sentences[i + 1:]
            break

    if not greeting and len(sentences) > 3:
        greeting = sentences[0]
        sentences = sentences[1:]

    body = " ".join(sentences)

    return {
        "greeting": greeting,
        "body": body,
        "closing": closing,
        "images": images,
    }