# Open WebUI integration

Этот пакет отделяет внешнее LLM-взаимодействие от локального анализа письма.

```text
ai_integration/
├── config.py   # Settings и `.env`
├── client.py   # HTTP client, JSON parsing, segmentation и AI judge
└── __init__.py # public API
```

`OPENWEBUI_BASE_URL`, `OPENWEBUI_MODEL` и `OPENWEBUI_API_KEY` читаются из `.env` через `pydantic-settings`. Внешняя переменная окружения имеет приоритет над `.env`.

Публичные функции:

- `OpenWebUIClient` — OpenAI-compatible HTTP transport;
- `segment_email()` — semantic segmentation;
- `ai_judge()` — отдельный LLM-вердикт;
- `analyze_with_ai()` — orchestration двух задач.

LLM verdict не изменяет локальные эвристические scores в `email_analysis`.
