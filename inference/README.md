# Forensic EML pipeline

`inference/` — отдельный forensic-конвейер для анализа **одного** письма `.eml`. Он извлекает MIME-текст, HTML и изображения, запускает локальный классификатор AI-изображений и записывает timestamped JSON-отчёт.

Это не тот же сценарий, что корневой `main.py`: `main.py` выполняет heuristic batch-анализ спама, фишинга и AI-похожего текста; `inference/` ориентирован на сохранение происхождения артефактов конкретного `.eml` и на image forensics.

## Возможности и границы

| Возможность | Состояние | Реализация |
|---|---|---|
| Чтение `.eml`, `text/plain`, `text/html`, metadata | готово | `extraction.py` → `parse_eml()` |
| MIME image attachments и HTML `data:image/...;base64` | готово | `extraction.py` |
| Лимиты числа и размера изображений | готово | `config.py`, `extraction.py` |
| Локальная классификация изображений `ai` / `real` | готово | `image_analysis.py`, `image_analyzer.py` |
| Отчёт JSON и запись через временный файл | готово | `reporting.py` → `save_report()` |
| AI-детекция текста, сегментация, OCR | не реализовано | text artifacts получают `not_implemented` |
| PDF/DOCX/XLSX/PPTX, ZIP recursion | не реализовано | `service.py` → `process_non_image_attachments()` |
| LLM/Qwen explanation | класс существует, но не подключён к `process_email()` | `image_analyzer.py` → `QwenImageExplainer` |

`contains_ai_content` означает, что локальный detector нашёл AI-классифицированное **изображение**. Это не доказательство, что всё письмо создано AI. `insufficient_evidence` не означает «контент человеческий»: он означает, что ни один доступный detector не обработал релевантный артефакт.

## Структура и поток данных

```text
inference/
├── pipeline.py        CLI и обратная совместимость
├── service.py         process_email(): orchestration, cleanup, lifecycle report
├── config.py          DEFAULT_CONFIG и merge_config()
├── extraction.py      MIME/data-URI extraction во временную директорию
├── text_artifacts.py  text provenance и placeholder text analysis
├── image_analysis.py  адаптер между extracted Path и ImageDetector
├── image_analyzer.py  MobileNetV3 detector и необязательный Qwen explainer
├── reporting.py       aggregation и atomic JSON persistence
└── artifacts.py       единый вид error/skipped artifacts
```

```text
.eml
→ extraction.parse_eml()
→ text_artifacts.build_text_artifacts()
→ image_analysis.analyze_images()
→ reporting.determine_overall_ruling()
→ service.process_email()
→ forensic_reports/<UTC timestamp>_<subject>_<id>.json
```

Ошибки отдельной MIME-части или одного изображения не останавливают письмо: они сохраняются в `errors` или `artifacts`. Только фатальная ошибка самого письма устанавливает `analysis.status = "failed"`.

## Требования

- Python 3.12+;
- зависимости из корневого `requirements.txt`;
- для image detection: `torch`, `torchvision`, `pillow`;
- checkpoint: `models/ai_image_detector_mobilenet_v3_small.pth`.

Запускайте команды из **корня репозитория** `AISpamEmail`. Это важно для импорта пакета `inference` и относительных путей к `samples/` и `models/`.

## Windows: установка и запуск

### Обычный Python + venv

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\.venv\Scripts\python.exe -m pip install torch torchvision pillow

.\.venv\Scripts\python.exe -m inference.pipeline `
  .\samples\ru_test_email.eml `
  -o .\forensic_reports
```

Активация `.venv` необязательна. Если она нужна и PowerShell блокирует `Activate.ps1`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### uv

```powershell
uv venv --python 3.12
uv pip install -r .\requirements.txt
uv pip install torch torchvision pillow
uv run python -m inference.pipeline .\samples\ru_test_email.eml -o .\forensic_reports
```

## Linux/macOS: установка и запуск

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install torch torchvision pillow

.venv/bin/python -m inference.pipeline \
  ./samples/ru_test_email.eml \
  -o ./forensic_reports
```

Или после `source .venv/bin/activate` используйте `python -m inference.pipeline ...`.

## CLI

Основной вариант:

```text
python -m inference.pipeline INPUT.eml [-o OUTPUT_DIRECTORY]
```

```powershell
# Рекомендуемый запуск как Python package.
.\.venv\Scripts\python.exe -m inference.pipeline .\samples\ru_test_email.eml -o .\forensic_reports

# Legacy-вызов также поддержан.
.\.venv\Scripts\python.exe .\inference\pipeline.py .\samples\ru_test_email.eml -o .\forensic_reports
```

Коды завершения:

| Код | Значение |
|---:|---|
| `0` | Отчёт создан, `analysis.status = completed` |
| `1` | Отчёт создан, но EML-level анализ завершился `failed` |
| `2` | Даже отчёт создать не удалось |

## Проверка image detector

Текущие файлы в `samples/` не содержат изображений, поэтому они проверяют MIME/text/reporting, но не MobileNet. Для полной проверки создайте письмо с inline-image или image attachment через `tools/makeeml.py`:

```powershell
.\.venv\Scripts\python.exe .\tools\makeeml.py
```

Сохраните его как `samples/image_test.eml`, затем запустите pipeline. При успешной обработке в JSON появится:

```json
{
  "id": "image-0001",
  "type": "image",
  "status": "analyzed",
  "ruling": {
    "classification": {
      "label": "ai",
      "score": 0.91
    }
  }
}
```

`label = "real"` также является успешной обработкой. Если detector отключён или checkpoint не загрузился, соответствующий artifact будет `skipped` или `error`; весь отчёт при этом останется `completed`.

## Конфигурация Python API

CLI использует `DEFAULT_CONFIG` из `config.py`. Для изменения параметров вызывайте `process_email()` программно:

```python
from inference import process_email

report = process_email(
    "samples/image_test.eml",
    output_dir="forensic_reports",
    config={
        "image_checkpoint": "models/ai_image_detector_mobilenet_v3_small.pth",
        "image_architecture": "mobilenet_v3_small",
        "image_threshold": 0.60,
        "max_image_bytes": 10 * 1024 * 1024,
        "keep_temp_files": False,
    },
)
print(report["ruling"])
```

| Параметр | По умолчанию | Назначение |
|---|---:|---|
| `image_analyzer_enabled` | `True` | Включает локальный анализ картинок |
| `image_checkpoint` | `models/ai_image_detector_mobilenet_v3_small.pth` | Путь к checkpoint |
| `image_architecture` | `mobilenet_v3_small` | Архитектура checkpoint; должна с ним совпадать |
| `image_threshold` | `0.5` | `sigmoid(logit) >= threshold` означает `ai` |
| `max_html_inline_images` | `100` | Лимит data-URI изображений из HTML |
| `max_image_bytes` | `25 MiB` | Лимит одного изображения |
| `max_total_extracted_bytes` | `200 MiB` | Общий лимит извлечённых изображений |
| `keep_temp_files` | `False` | Оставить извлечённые временные файлы для отладки |

Можно передать свой `image_analyzer: Callable[[Path, dict], dict]` в `config`; он заменит загрузку локальной модели.

## Формат результата

Отчёт содержит:

- `analysis` — UUID, UTC-времена, `completed`/`failed`;
- `input` — имя и абсолютный путь входного файла;
- `email_metadata` — `subject`, `from`, `to`, `cc`, `date`, `message_id`;
- `artifacts` — text/image результаты и их status;
- `errors` — нефатальные ошибки извлечения;
- `ruling` — текущий email-level verdict;
- `extensions` — явно обозначенные незавершённые направления;
- `output.report_path` — абсолютный путь уже сохранённого отчёта.

Тело письма намеренно не записывается в final report. Это снижает риск хранения чувствительного содержимого в forensic JSON.

## Диагностика

### `ModuleNotFoundError: No module named 'inference'`

Запуск выполнен не из корня репозитория. Перейдите в `AISpamEmail` и используйте `python -m inference.pipeline ...`. Legacy-команда `python inference/pipeline.py ...` также поддерживается.

### `No module named torch` / `torchvision` / `PIL`

Установите image dependencies в то же окружение, которым запускаете pipeline:

```powershell
.\.venv\Scripts\python.exe -m pip install torch torchvision pillow
```

### `status = completed`, но `ruling = insufficient_evidence`

Это ожидаемо для письма без успешно проанализированных изображений. Проверьте `artifacts` и `errors`; text detector ещё не реализован.

### Кириллическая тема отображается как `ÐŸ...` в Windows PowerShell

Отчёт записан в UTF-8. Прочитайте его явно в UTF-8:

```powershell
Get-Content .\forensic_reports\report.json -Raw -Encoding UTF8 | ConvertFrom-Json
```

### `status = failed`

Откройте `errors[0].error` в созданном JSON: это EML-level ошибка. Отдельная ошибка картинки не должна приводить к `failed`.
