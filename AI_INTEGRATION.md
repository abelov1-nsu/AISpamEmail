# Интеграция Open WebUI (смысловая сегментация + AI judge)

## Что добавляется в отчёт

По каждому письму в JSON появляются поля:

### `segments` — смысловые абзацы

Массив объектов вида:

```json
[
  {
    "type": "subject",
    "content": "Тема письма",
    "pos": 0
  },
  {
    "type": "greeting",
    "content": "Здравствуйте!",
    "pos": 1
  },
  {
    "type": "main_body",
    "content": "Основной текст...",
    "pos": 2
  },
  {
    "type": "farewell",
    "content": "С уважением, ...",
    "pos": 3
  }
]
```

Типы (`type`) модель выбирает сама по смыслу. Возможные значения:
`subject`, `greeting`, `introduction`, `main_body`, `request`, `offer`, `warning`, `cta`, `farewell`, `signature`, `disclaimer`, `ps`, `attachment_note`, `other` и другие короткие метки.

### `has_images`

`true` / `false` — есть ли картинки / вложения-изображения.

### `ai_judge`

```json
{
  "is_ai_generated": true,
  "confidence": 0.87,
  "label": "likely_ai",
  "reasoning": "...",
  "suspicious_parts": ["greeting", "main_body"]
}
```

Вердикт **не меняет** старые scores — это отдельное поле.

---

## Настройка

```bash
export OPENWEBUI_BASE_URL="http://localhost:3000"
export OPENWEBUI_MODEL="Qwen3.8-Flash-Next"
export OPENWEBUI_API_KEY="sk-..."          # если нужна авторизация
```

## Запуск

```bash
pip install requests

# демо
python main.py --demo --use-ai

# папка с .eml
python main.py --dataset ./samples --output ./analysis_results --use-ai
```

Без `--use-ai` всё работает как раньше.
