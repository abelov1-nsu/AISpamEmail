# AISpamEmail: Анализ email-писем на спам, фишинг и AI-контент

Комплексный инструмент для выявления спама, фишинга и AI-сгенерированного контента в письмах формата `.eml`.

Архитектура проекта декомпозирована на специализированные модули:
* **`email_analysis`** — эвристический анализ писем (URL, стилометрия, спам/фишинг паттерны, повторы) и пакетная обработка;
* **`ai_integration`** — клиент к Open WebUI / OpenAI API для семантической сегментации и LLM-judge;
* **`inference`** — forensic-конвейер детального пофайлового анализа одного письма с извлечением вложений и классификацией изображений;
* **`models`** — архитектура и скрипты обучения детектора AI-сгенерированных изображений (MobileNetV3 / EfficientNet);
* **`dataset`** — скрипты подготовки данных и построения baseline-классификаторов.

---

## Сводная таблица сценариев запуска

| Сценарий | Команда | Результат |
|---|---|---|
| **Пакетный эвристический анализ** | `python main.py --dataset samples --output analysis_results` | Обработка каталога писем, формирование JSON-отчётов и `summary.json` |
| **Демо-анализ через фасад** | `python main.py --demo` | Расчёт spam, phishing и ai-assisted scores на встроенных синтетических примерах |
| **Демо-анализ через пакет** | `python -m email_analysis --demo` | Запуск анализа напрямую через модуль `email_analysis` |
| **Справка CLI модуля** | `python -m email_analysis.cli --help` | Справка CLI-адаптера эвристического анализатора |
| **Forensic EML конвейер** | `python -m inference.pipeline .\samples\ru_test_email.eml -o .\forensic_test` | Извлечение MIME, артефактов и классификация AI-изображений с JSON-отчётом |
| **Загрузка чекпоинта MobileNetV3** | `python -c "from inference.image_analyzer import ImageDetector; from inference.config import DEFAULT_CONFIG; ImageDetector(DEFAULT_CONFIG['image_checkpoint'])"` | Проверка загрузки обученного чекпоинта на устройство |
| **Обучение детектора** | `python -m models.scripts.train_image_detector --help` | Справка по обучению детектора изображений FAKE-vs-REAL |
| **Импорт всех пакетов** | `python -c "import ai_integration, email_analysis, inference, models"` | Проверка целостности импортов и отсутствия циклических зависимостей |

> Полное руководство по установке окружения, настройке `.env` и опциям см. в [docs/USAGE.md](file:///d:/NSU/PROJECTS/AISpamEmail/docs/USAGE.md).

---

## Быстрый старт

### 1. Установка окружения

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

*(или с использованием `uv`: `uv venv --python 3.12 && uv pip install -r requirements.txt`)*

### 2. Запуск эвристического анализа

```powershell
# Запуск демонстрации на синтетических данных
python main.py --demo

# Анализ папки с реальными письмами
python main.py --dataset samples --output analysis_results
```

### 3. Запуск forensic-анализа конкретного письма

```powershell
python -m inference.pipeline samples/ru_test_email.eml -o forensic_reports
```

Как это работает (коротко)

    Парсинг — email.policy.default, метаданные + обход MIME-частей (text/plain, text/html, image/*).

    Извлечение — MIME-картинки во временную папку (с лимитами по размеру); inline data:image/...;base64 декодируются из HTML.

    Текст — формируются артефакты plain и HTML→text. Анализ текста пока не реализован (TODO), контент в отчёт не попадает.

    Картинки — analyze_image(path, config) на каждую; ошибка одной не роняет остальные.

    Агрегация — консервативный вывод уровня письма (пока только по картинкам).

    Отчёт — атомарная запись .tmp → os.replace.

    Очистка — временная папка удаляется в finally, если keep_temp_files=False.

Конфиг (топ-значения)
Ключ	По умолчанию	Смысл
image_analyzer_enabled	True	Запускать локальный детектор
use_llm	True	LLM-слой внутри image_analyzer
llm_provider	"openai"	"openai" или "ollama"
ollama_model	"llava:7b"	Модель Ollama
openai_model	"gpt-4o-mini"	Модель OpenAI-совместимая
output_dir	"forensic_reports"	Куда писать отчёты
max_image_bytes	25 MiB	Лимит на картинку
max_total_extracted_bytes	200 MiB	Лимит на письмо
keep_temp_files	False	Оставить временные файлы для отладки
Коды выхода
Код	Значение
0	Отчёт создан, status == "completed"
1	Отчёт создан, status == "failed"
2	Отчёт вообще не удалось создать (например, файл не найден)
Что пока НЕ реализовано (TODO в коде)

    AI-детекция текста

    PDF / DOCX / XLSX / PPTX / ZIP (с рекурсией)

    OCR сканированных документов

    Мелкая сегментация текста (абзацы/предложения со смещениями)

    Взвешенная агрегация по тексту + картинкам + документам

Важно про интерпретацию

Метка уровня письма описывает найденный в письме контент, а не «всё письмо сгенерировано AI». Текущая логика — только по картинкам и консервативная:

    есть сильная AI-картинка → contains_ai_content

    картинки проанализированы, сильных нет → no_ai_detected_in_analyzed_images

    нет успешно проанализированных артефактов → insufficient_evidence

Это сигнал для расследования, а не доказательство.
