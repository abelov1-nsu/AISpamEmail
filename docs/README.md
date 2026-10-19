Email AI-Content Forensic Pipeline

Пайплайн для анализа .eml файлов на предмет AI-сгенерированного контента. Разбирает тело письма, извлекает MIME- и inline (data-URI) изображения, прогоняет их через локальный детектор (image_analyzer), опционально — через LLM (OpenAI-совместимый или локальный Ollama/Qwen), и пишет JSON-отчёт с временной меткой.

Устойчив к ошибкам: падение одного артефакта не останавливает обработку письма, отчёт всё равно будет создан.
Требования

    Python 3.10+

    Модуль image_analyzer.py рядом с pipeline.py (должен экспортировать analyze_image(path: str, config: dict) -> dict)

    Опционально для LLM-слоя: OPENAI_API_KEY или запущенный Ollama с vision-моделью (например, llava:7b)

Пайплайн использует только стандартную библиотеку Python. В requirements.txt кладите зависимости вашего image_analyzer и LLM-клиентов.

# image detection / ML (адаптируйте под свой image_analyzer)
torch
torchvision
pillow
numpy

# optional LLM layer
openai
requests
ollama

Установка
bash

python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\Activate.ps1     # Windows PowerShell

pip install --upgrade pip
pip install -r requirements.txt

# только если use_llm включён
export OPENAI_API_KEY="sk-..."

**Быстрый старт**
1. Получение примеров .eml

    Gmail: открыть письмо → ⋮ → Download message

    Thunderbird: правый клик → Save As → .eml

    Outlook: File → Save As → MIME / .eml

bash

mkdir -p samples
cp ~/Downloads/my_message.eml samples/example.eml

2. Запустите
bash

python pipeline.py samples/example.eml
# или с явной папкой вывода:
python pipeline.py samples/example.eml -o ./forensic_reports

На stdout придёт краткая сводка:
json

{
  "status": "completed",
  "ruling": {
    "label": "no_ai_detected_in_analyzed_images",
    "strongest_ai_score": 0.0,
    "basis": "image_detector"
  },
  "report": "/abs/path/forensic_reports/20260101T120000Z_Subject_ab12cd34.json"
}

3. Отчёт

Лежит в forensic_reports/ — <UTC-timestamp>_<subject>_<uuid8>.json. Ключевые поля:
Поле	Значение
analysis.status	completed или failed
email_metadata	Subject, From, To, Cc, Date, Message-ID
artifacts[]	По одной записи на текст/HTML/картинку со своим status и ruling
errors[]	Нефатальные ошибки извлечения
ruling	Агрегированный вывод по письму
4. Как библиотека
python

from pipeline import process_email

report = process_email(
    "samples/example.eml",
    output_dir="forensic_reports",
    config={"use_llm": True, "llm_provider": "openai"},
)
print(report["ruling"]["label"])
print(report["output"]["report_path"])

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
