import re
import os
import numpy as np

from email_parser import (
    parse_email_structure,
)

# Опциональный OCR
try:
    import easyocr
    from PIL import Image
    import urllib.request
    HAS_OCR = True
    # Инициализируем лениво (только при первом вызове)
    _reader = None
    def _get_reader():
        global _reader
        if _reader is None:
            _reader = easyocr.Reader(['en', 'ru'], gpu=False)
        return _reader
except ImportError:
    HAS_OCR = False


# ====================== РЕГУЛЯРКИ ======================
URL_RE = re.compile(r"https?://\S+|www\.\S+")
HTML_RE = re.compile(r"<[a-zA-Z/][^>]*>")
EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
MONEY_RE = re.compile(r"[$€₽£]\s?\d+")
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
LATIN_RE = re.compile(r"[A-Za-z]")


# ====================== 1. СТРУКТУРНЫЕ (12) ======================
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
        "срочно", "немедленно", "сегодня", "успейте",
        "истекает", "ограничено", "последний шанс",
        "подтвердите", "верифицируйте", "заблокирован", "приостановлен",
    ]
    t = text.lower()
    return sum(1 for w in words if w in t)


# ====================== 2. ТЕКСТОВЫЕ (5) ======================
def politeness_markers(text: str) -> int:
    markers = [
        "dear", "hello", "hi", "best regards", "sincerely",
        "kind regards", "thank you", "please", "kindly",
        "здравствуйте", "привет", "с уважением", "спасибо",
        "пожалуйста", "будьте добры", "благодарю",
    ]
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
        "надеюсь, у вас всё хорошо",
        "надеюсь, данное письмо застанет вас",
        "я пишу вам, чтобы",
        "не стесняйтесь обращаться",
        "заранее благодарю за ответ",
        "рады сообщить",
        "сообщаем вам, что",
        "просим вас",
    ]
    t = text.lower()
    return sum(1 for p in phrases if p in t)

def avg_word_length(text: str) -> float:
    words = text.split()
    if not words:
        return 0.0
    return sum(len(w) for w in words) / len(words)

def sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?…]+", text))

def avg_sentence_length(text: str) -> float:
    sentences = re.split(r"[.!?…]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)


# ====================== 3. PARTIAL AI (3) ======================
def style_shift_score(text: str) -> float:
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
    formal_words = {
        "regarding", "furthermore", "therefore", "however", "moreover",
        "касательно", "более того", "следовательно", "однако", "кроме того",
    }
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
    score = 0
    score += len(re.findall(r"\s{2,}", text))
    score += len(re.findall(r"\bi\b", text))
    score += len(re.findall(r"([a-zа-я])\1{2,}", text))
    return score


# ====================== 4. РЕГИОНАЛЬНЫЕ (7) ======================
def script_type(text: str) -> int:
    has_latin = bool(LATIN_RE.search(text))
    has_cyr = bool(CYRILLIC_RE.search(text))
    if has_latin and has_cyr:
        return 2
    if has_cyr:
        return 1
    if has_latin:
        return 0
    return 3

def currency_diversity(text: str) -> int:
    currencies = ["$", "€", "₽", "£", "¥", "₹", "₴", "₸"]
    return sum(1 for c in currencies if c in text)

def country_tld(text: str) -> int:
    tlds = [".ru", ".de", ".cn", ".fr", ".uk", ".jp", ".br", ".in"]
    return sum(1 for t in tlds if t in text.lower())

def local_authority(text: str) -> int:
    markers = [
        "irs", "finanzamt", "hmrc", "cra", "ato",
        "фнс", "пфр", "сбербанк",
        "chase", "barclays", "deutsche bank",
    ]
    t = text.lower()
    return sum(1 for m in markers if m in t)

def timezone_marker(text: str) -> int:
    markers = [
        "moscow time", "cet", "pst", "est", "gmt", "utc+", "msk",
        "мск", "московское время",
    ]
    t = text.lower()
    return sum(1 for m in markers if m in t)

def holiday_marker(text: str) -> int:
    markers = [
        "new year", "christmas", "lunar new year", "easter", "black friday",
        "новый год", "рождество", "8 марта", "23 февраля", "пасха",
    ]
    t = text.lower()
    return sum(1 for m in markers if m in t)

def regional_keywords(text: str) -> int:
    markers = [
        "moscow", "berlin", "beijing", "london", "paris", "tokyo",
        "москва", "берлин", "пекин", "лондон", "париж",
    ]
    t = text.lower()
    return sum(1 for m in markers if m in t)


# ====================== 5. ФОРМАЛЬНОСТЬ (2) ======================
def formality_score(text: str) -> float:
    formal = {
        "regarding", "furthermore", "therefore", "however", "moreover",
        "accordingly", "consequently", "pursuant", "henceforth",
        "касательно", "более того", "следовательно", "однако", "кроме того",
        "соответственно", "в соответствии",
    }
    words = text.lower().split()
    if not words:
        return 0.0
    return sum(1 for w in words if w in formal) / len(words)

def informality_score(text: str) -> float:
    informal = {
        "hey", "yeah", "wanna", "gonna", "btw", "lol", "omg", "yo",
        "приветик", "блин", "круто", "ок", "ладно", "ну",
    }
    words = text.lower().split()
    if not words:
        return 0.0
    return sum(1 for w in words if w in informal) / len(words)


# ====================== 6. СТРУКТУРНЫЙ ПАРСЕР (3) ======================
def structure_perfection(text: str) -> int:
    parts = parse_email_structure(text)
    score = 0
    if len(parts["greeting"]) > 5: score += 1
    if len(parts["body"]) > 20: score += 1
    if len(parts["closing"]) > 3: score += 1
    return score

def greeting_ai_pattern(text: str) -> int:
    parts = parse_email_structure(text)
    greeting = parts["greeting"].lower()
    ai_greetings = [
        "i hope this email finds you well",
        "dear valued customer", "dear user",
        "надеюсь, у вас всё хорошо", "уважаемый клиент", "уважаемый пользователь",
    ]
    return int(any(g in greeting for g in ai_greetings))

def closing_ai_pattern(text: str) -> int:
    parts = parse_email_structure(text)
    closing = parts["closing"].lower()
    ai_closings = [
        "best regards", "kind regards", "sincerely",
        "looking forward to hearing from you",
        "с уважением", "с наилучшими пожеланиями",
        "заранее благодарю",
    ]
    return int(any(c in closing for c in ai_closings))


# ====================== 7. КАРТИНКИ (3) ======================
def _download_image(url: str, save_path: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            with open(save_path, 'wb') as f:
                f.write(response.read())
        return True
    except Exception:
        return False

def _analyze_image(image_path: str) -> dict:
    result = {"text": "", "has_qr": 0}
    if not os.path.exists(image_path):
        return result
    try:
        with Image.open(image_path) as img:
            w, h = img.size
        
        if HAS_OCR:
            reader = _get_reader()
            ocr_results = reader.readtext(image_path, detail=0)
            result["text"] = " ".join(ocr_results)
            
        # Грубая эвристика на QR: квадратное изображение + короткий текст
        if w == h and len(result["text"]) < 50:
            result["has_qr"] = 1
    except Exception:
        pass
    return result

def process_images(images: list) -> dict:
    if not images:
        return {"image_count": 0, "image_text_len": 0, "has_qr": 0}
    
    total_text = ""
    has_qr = 0
    os.makedirs("data/temp_images", exist_ok=True)
    
    for i, url in enumerate(images):
        save_path = f"data/temp_images/tmp_{i}.jpg"
        if _download_image(url, save_path):
            info = _analyze_image(save_path)
            total_text += " " + info["text"]
            if info["has_qr"]:
                has_qr = 1
            if os.path.exists(save_path):
                os.remove(save_path)
                
    return {
        "image_count": len(images),
        "image_text_len": len(total_text.strip()),
        "has_qr": has_qr
    }


# ====================== ГЛАВНАЯ ФУНКЦИЯ ======================
def extract_features(subject: str, body: str, cta: str) -> dict:
    """
    Извлекает 35 признаков. Работает с EN и RU.
    """
    text = f"{subject} {body} {cta}"
    
    # Анализ картинок
    parts = parse_email_structure(text)
    img_info = process_images(parts.get("images", []))

    return {
        # 1. структурные (12)
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

        # 2. текстовые (5)
        "politeness_markers": politeness_markers(text),
        "ai_phrases": ai_phrases(text),
        "avg_word_length": avg_word_length(text),
        "sentence_count": sentence_count(text),
        "avg_sentence_length": avg_sentence_length(text),

        # 3. partial AI (3)
        "style_shift_score": style_shift_score(text),
        "formality_shift": formality_shift(text),
        "human_typos": human_typos(text),

        # 4. региональные (7)
        "script_type": script_type(text),
        "currency_diversity": currency_diversity(text),
        "country_tld": country_tld(text),
        "local_authority": local_authority(text),
        "timezone_marker": timezone_marker(text),
        "holiday_marker": holiday_marker(text),
        "regional_keywords": regional_keywords(text),

        # 5. формальность / неформальность (2)
        "formality_score": formality_score(text),
        "informality_score": informality_score(text),

        # 6. структура (3)
        "structure_perfection": structure_perfection(text),
        "greeting_ai_pattern": greeting_ai_pattern(text),
        "closing_ai_pattern": closing_ai_pattern(text),

        # 7. картинки (3)
        "image_count": img_info["image_count"],
        "image_text_len": img_info["image_text_len"],
        "has_qr": img_info["has_qr"],
    }
