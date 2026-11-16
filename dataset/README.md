# Dataset workspace

Этот модуль изолирует подготовку датасета и эксперименты с baseline-классификатором от runtime-анализатора в `main.py`.

```text
dataset/
├── data/
│   ├── raw/        # исходные файлы поставщиков; не коммитятся
│   └── processed/  # нормализованные CSV и feature matrix
├── reports/        # метрики, SHAP-графики, отчёты; не коммитятся
├── scripts/        # запускаемые сценарии
└── src/            # импортируемый код признаков и парсинга
```

## Контракты данных

- `data/raw/` — ожидает исходные наборы SpamAssassin, AI-spam, partially-AI и Enron. Имена входных файлов описаны в `scripts/build_dataset.py`.
- `data/processed/dataset.csv` — результат нормализации и балансировки исходных наборов.
- `data/processed/dataset_clean.csv` — текущий curated-набор для интерактивного baseline-предсказания.
- `data/processed/features.csv` и `data/processed/labels.csv` — feature matrix и метки для `train_baseline.py` и `explain_baseline.py`; в репозитории пока не создаются ни одним скриптом, поэтому их нужно подготовить отдельно.

`src.text_features.extract_features()` не скачивает изображения и не запускает OCR по умолчанию. Для этого нужен явный вызов с `analyze_remote_images=True` в доверенном окружении: обучающий набор может содержать произвольные URL.

## Запуск

Все сценарии запускаются из корня репозитория как Python-модули, чтобы импорты и пути не зависели от рабочей директории:

```powershell
.\.venv\Scripts\python.exe -m dataset.scripts.inspect_clean_dataset
.\.venv\Scripts\python.exe -m dataset.scripts.predict_email
.\.venv\Scripts\python.exe -m dataset.scripts.build_dataset
```

Для `train_baseline` и `explain_baseline` требуются `features.csv` и `labels.csv` из контракта выше.
