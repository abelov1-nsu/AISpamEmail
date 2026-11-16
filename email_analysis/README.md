# Email heuristic analysis

Этот пакет отвечает за batch-анализ `.eml`: MIME parsing, URL/HTML/style signals, heuristic spam/phishing/AI scores, optional Open WebUI enrichment и JSON outputs.

Текущий переходный layout:

```text
email_analysis/
├── application.py  # parser, analyzers, batch service и demo
├── cli.py          # argparse адаптер
├── __main__.py     # точка входа для python -m email_analysis
└── __init__.py     # public API
```

`main.py` сохранён как CLI compatibility entry point. В `application.py` ещё находятся эвристики и batch orchestration; следующий безопасный перенос внутри пакета: `parsing.py` (EmailParser), `signals.py` (URL/HTML/style/spam/phishing), `models.py` (dataclasses) и `service.py` (EmailAnalyzer). Формулы и пороги должны переноситься без изменения, после чего добавляются regression tests на `samples/`.
