# AISpamEmail: установка и запуск

## Назначение

Проект анализирует письма в формате `.eml` по нескольким независимым группам признаков:

- спам-фразы и призывы к действию;
- признаки фишинга и подозрительные URL;
- эвристические признаки AI-похожего текста;
- дополнительная сегментация текста и AI-оценка через Open WebUI.

Основная точка входа — `main.py`. Он сохраняет JSON-отчёт для каждого письма и общий `summary.json`.

## Требования

- Windows PowerShell, macOS Terminal, Linux shell или аналогичный terminal;
- Python 3.12+ (зафиксированный `contourpy==1.4.0` не поддерживает Python 3.11);
- доступ к Open WebUI/OpenAI-compatible API только для режима `--use-ai`.

Проверьте версию интерпретатора до установки зависимостей:

```powershell
python --version
```

На Windows, если `python` открывает Microsoft Store или не найден, используйте Python Launcher:

```powershell
py -3.12 --version
```

Ниже приведены равноправные способы установки. Выберите **один**; не смешивайте пакеты из разных окружений.

## Установка через uv

Выполняйте команды из корня репозитория:

```powershell
uv venv --python 3.12
uv pip install -r .\requirements.txt
```

Если стандартный cache `uv` недоступен:

```powershell
uv pip install --cache-dir .uv-cache -r .\requirements.txt
```

Активация виртуального окружения не обязательна. Запуск:

```powershell
uv run python main.py --demo
```

## Установка через стандартный Python и `venv`

Этот вариант подходит, если `uv` не установлен. Выполняйте команды из корня проекта.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

Запуск без активации:

```powershell
.\.venv\Scripts\python.exe main.py --demo
```

Альтернативно можно активировать окружение:

```powershell
.\.venv\Scripts\Activate.ps1
python main.py --demo
```

### macOS и Linux

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --demo
```

Либо активируйте окружение:

```bash
source .venv/bin/activate
python main.py --demo
```

## Установка через Conda

Подходит, когда Python управляется Anaconda/Miniconda:

```powershell
conda create -n aispamemail python=3.12 -y
conda activate aispamemail
python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
python main.py --demo
```

## Запуск без виртуального окружения

Этот способ допустим только для быстрого локального эксперимента: зависимости будут установлены в выбранный системный Python и могут конфликтовать с другими проектами.

```powershell
py -3.12 -m pip install -r .\requirements.txt
py -3.12 main.py --demo
```

На macOS/Linux:

```bash
python3.12 -m pip install -r requirements.txt
python3.12 main.py --demo
```

Во всех последующих командах `uv run python` можно заменить на один из вариантов:

| Среда | Команда Python |
|---|---|
| `uv` | `uv run python` |
| Windows `venv`, без активации | `.\.venv\Scripts\python.exe` |
| Windows `venv`, после активации | `python` |
| macOS/Linux `venv`, без активации | `.venv/bin/python` |
| Conda или системный Python | `python` / `python3.12` |

## Конфигурация `.env`

Создайте файл `.env` в корне проекта:

```dotenv
OPENWEBUI_BASE_URL=NSU
OPENWEBUI_MODEL=Qwen3.8-27B
OPENWEBUI_API_KEY=your_api_key
```

Переменные:

| Переменная | Обязательность | Назначение |
|---|---|---|
| `OPENWEBUI_BASE_URL` | для `--use-ai` | Базовый URL сервера, без `/api/chat/completions` |
| `OPENWEBUI_MODEL` | для `--use-ai` | Точный `id` модели из API сервера |
| `OPENWEBUI_API_KEY` | зависит от сервера | Bearer-токен; оставьте пустым, если авторизация отключена |

Настройки загружаются в `ai_integration` через `pydantic-settings`. Явные переменные окружения имеют приоритет над `.env`. Не коммитьте настоящий API-ключ.

Проверка конфигурации без вывода самого ключа:

```powershell
python -c "from ai_integration import settings; print(settings.openwebui_base_url); print(settings.openwebui_model); print('api_key_present=', bool(settings.openwebui_api_key))"
```

Проверка доступных моделей:

```powershell
$headers = @{ Authorization = "Bearer $env:OPENWEBUI_API_KEY" }
Invoke-RestMethod -Uri "$env:OPENWEBUI_BASE_URL/api/models" -Headers $headers
```

## Сводная таблица сценариев запуска и самодиагностики

Для быстрой проверки работоспособности модулей, воспроизведения сценариев анализа и валидации целостности используйте команды из таблицы:

| Сценарий | Команда | Результат / Описание |
|---|---|---|
| **Пакетный эвристический анализ** | `python main.py --dataset samples --output analysis_results` | Успешно (обработаны письма, сформирован `summary.json`) |
| **Демо-анализ через фасад** | `python main.py --demo` | Успешно (рассчитаны spam, phishing и ai-assisted scores на синтетических примерах) |
| **Демо-анализ через пакет** | `python -m email_analysis --demo` | Успешно (прямой запуск логики через модуль `email_analysis`) |
| **Справка CLI модуля** | `python -m email_analysis.cli --help` | Успешно (вывод параметров CLI эвристического анализатора) |
| **Forensic EML конвейер** | `python -m inference.pipeline .\samples\ru_test_email.eml -o .\forensic_test` | Успешно (извлечение MIME, артефактов, классификация AI-изображений и отчёт) |
| **Загрузка чекпоинта MobileNetV3** | `python -c "from inference.image_analyzer import ImageDetector; from inference.config import DEFAULT_CONFIG; ImageDetector(DEFAULT_CONFIG['image_checkpoint'])"` | Чекпоинт успешно загружен на устройство (CPU/CUDA) |
| **Обучение детектора** | `python -m models.scripts.train_image_detector --help` | Успешно (справка и валидация скрипта обучения MobileNetV3 FAKE-vs-REAL) |
| **Импорт всех пакетов** | `python -c "import ai_integration, email_analysis, inference, models"` | Импортируются чисто, циклических зависимостей нет |

## Режимы запуска

### 1. Встроенный demo без LLM

Проверяет локальную эвристику на синтетических письмах:

```powershell
uv run python main.py --demo
```

Без `uv`, например в Windows `venv`:

```powershell
.\.venv\Scripts\python.exe main.py --demo
```

### 2. Встроенный demo с LLM

Дополнительно вызывает Open WebUI для семантической сегментации и AI judge:

```powershell
uv run python main.py --demo --use-ai
```

Без `uv`, используя Windows `venv`:

```powershell
.\.venv\Scripts\python.exe main.py --demo --use-ai
```

В результате появляются поля `segments`, `has_images` и `ai_judge`.

### 3. Анализ каталога `.eml` без LLM

Положите письма в `samples/` или другой каталог:

```powershell
uv run python main.py `
  --dataset .\samples `
  --output .\analysis_results
```

Без `uv`:

```powershell
.\.venv\Scripts\python.exe main.py `
  --dataset .\samples `
  --output .\analysis_results
```

### 4. Анализ каталога `.eml` с LLM

```powershell
uv run python main.py `
  --dataset .\samples `
  --output .\analysis_results `
  --use-ai
```

Без `uv`:

```powershell
.\.venv\Scripts\python.exe main.py `
  --dataset .\samples `
  --output .\analysis_results `
  --use-ai
```

Параметры:

- `--dataset` — каталог, который рекурсивно сканируется на `.eml`;
- `--output` — каталог JSON-результатов, по умолчанию `analysis_results`;
- `--demo` — встроенные тестовые письма;
- `--use-ai` — включить Open WebUI.

## Результаты

Для каждого письма создаётся JSON с полями:

- `spam_score` — эвристический score спама;
- `phishing_score` — эвристический score фишинга;
- `ai_assisted_score` — эвристический score AI-похожего текста;
- `judgement` — итоговая метка;
- `components` — URL, HTML, заголовки, стилометрия, CTA и повторяемость;
- `signals` — значения, веса и объяснения отдельных сигналов;
- `segments` — LLM-сегменты, если включён AI-режим;
- `ai_judge` — отдельный LLM-вердикт, который не изменяет старые score.

Допустимые итоговые значения `judgement`:

```text
likely_phishing
likely_spam
likely_ai_assisted
suspicious
inconclusive
```

В каталоге результата также создаётся `summary.json` со статистикой по обработанным письмам.

## Генерация тестового `.eml`

Локальный GUI-генератор находится в `tools/makeeml.py` и письма не отправляет:

```powershell
uv run python .\tools\makeeml.py
```

Без `uv`:

```powershell
.\.venv\Scripts\python.exe .\tools\makeeml.py
```

Сохраняйте созданные письма в `samples/`, затем повторно запускайте анализ каталога.

## Быстрая проверка LLM

Перед запуском проекта можно проверить endpoint минимальным запросом:

```powershell
$headers = @{
  Authorization = "Bearer $env:OPENWEBUI_API_KEY"
  "Content-Type" = "application/json"
}
$body = @{
  model = $env:OPENWEBUI_MODEL
  messages = @(@{ role = "user"; content = "Reply with exactly: OK" })
  stream = $false
} | ConvertTo-Json -Depth 5

(Invoke-RestMethod `
  -Uri "$env:OPENWEBUI_BASE_URL/api/chat/completions" `
  -Method Post -Headers $headers -Body $body).choices[0].message.content
```

Ожидаемый ответ — `OK`. Ошибка `Model not found` означает, что в `.env` указано не точное значение `id` модели.

## Типичные ошибки

### `contourpy ... requires Python>=3.12`

Окружение создано на Python 3.11. Пересоздайте его через `uv venv --python 3.12 --clear`.

### `Model not found`

Получите модели через `GET /api/models` и укажите точный `id` в `OPENWEBUI_MODEL`.

### `400 Bad Request` от chat endpoint

Проверьте URL, модель и совместимость сервера с OpenAI-compatible `/api/chat/completions`. В проекте для LLM включается JSON response format; некоторые серверы его не поддерживают.

### `ai_judge.label = error`

Локальная эвристика продолжает работать, но LLM-запрос завершился ошибкой. Смотрите поле `ai_judge.reasoning` в JSON-отчёте.

### PowerShell запрещает `Activate.ps1`

Активация не требуется. Используйте `uv run ...`. Либо разрешите скрипт только в текущем сеансе:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

