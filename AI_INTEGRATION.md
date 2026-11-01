# Интеграция Open WebUI (сегментация + AI judge)

Добавлены два новых поля в итоговый JSON-отчёт:

- `segmentation` — разбиение письма на:
  - `greeting` (приветствие)
  - `main_body` (основная часть)
  - `farewell` (прощание / подпись)
  - `has_images` (есть ли картинки)

- `ai_judge` — вердикт LLM:
  ```json
  {
    "is_ai_generated": true/false,
    "confidence": 0.0-1.0,
    "label": "likely_ai" | "possibly_ai" | "likely_human" | "inconclusive",
    "reasoning": "...",
    "suspicious_parts": ["greeting", "main_body", ...]
  }
  ```

Вердикт **не меняет** существующие scores (`spam_score`, `ai_assisted_score` и т.д.) — просто дополнительное поле.

## Настройка

В терминале перед запуском:

```bash
export OPENWEBUI_BASE_URL="http://localhost:3000"   # адрес твоего Open WebUI
export OPENWEBUI_MODEL="llama3.2"                   # имя модели как в UI
export OPENWEBUI_API_KEY="sk-..."                   # если включена авторизация
```

Если API-ключ не нужен — просто не задавай `OPENWEBUI_API_KEY`.

## Запуск

```bash
# демо с AI
python main.py --demo --use-ai

# анализ папки с .eml
python main.py --dataset ./samples --output ./analysis_results --use-ai
```

Без флага `--use-ai` всё работает как раньше (AI-часть пропускается).

## Как это устроено

Файл `ai_client.py`:
- `OpenWebUIClient` — тонкий клиент к `POST /api/chat/completions`
- `segment_email()` — промпт для разбиения на greeting / main_body / farewell
- `ai_judge()` — промпт для вердикта «сгенерировано ИИ или нет»
- `analyze_with_ai()` — удобная обёртка, которую вызывает `EmailAnalyzer`

В `EmailAnalyzer` добавлен параметр `use_ai=True`. При анализе письма вызывается LLM один раз на сегментацию и один раз на judge.

## Пример фрагмента отчёта

```json
{
  "email_id": "example.eml",
  "spam_score": 0.12,
  "phishing_score": 0.05,
  "ai_assisted_score": 0.68,
  "judgement": "suspicious",
  "segmentation": {
    "greeting": "Hello,",
    "main_body": "I hope this message finds you well. ...",
    "farewell": "Thank you for your understanding.",
    "has_images": false
  },
  "ai_judge": {
    "is_ai_generated": true,
    "confidence": 0.87,
    "label": "likely_ai",
    "reasoning": "Formulaic opening and closing, generic corporate tone...",
    "suspicious_parts": ["greeting", "main_body", "farewell"]
  }
}
```
