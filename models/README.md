# Image detector training

Этот каталог отвечает только за обучение классификатора изображений `REAL` против `FAKE/AI`. Runtime-инференс находится в `inference/image_analyzer.py`.

## Структура

```text
models/
├── image_detector/       # конфигурация, данные, модель, loops, metrics, checkpoint
├── scripts/              # CLI-скрипты обучения
├── checkpoints/          # сохранённые .pth
└── reports/image_detector/ # отчёты запусков
```

## Датасет

Пути передаются через CLI. Ожидается ImageFolder-структура:

```text
dataset-root/
├── train/
│   ├── FAKE/
│   └── REAL/
└── test/
    ├── FAKE/
    └── REAL/
```

Маппинг модели фиксирован: `REAL = 0`, `FAKE = 1`. Обучающая часть train делится на train/validation; `test/` не участвует в подборе checkpoint.

## Pipeline обучения

```text
CLI
→ TrainingConfig
→ ImageFolder + augmentation
→ train/validation split
→ MobileNetV3-Small, one binary logit
→ classifier warm-up
→ full-backbone fine-tuning
→ validation metrics and early stopping
→ best .pth checkpoint
→ final test metrics
```

Checkpoint сохраняет `model_state_dict`, архитектуру, mapping классов, размер изображения и validation metrics. Этот формат загружается `inference.image_analyzer.ImageDetector`.

## Запуск

Из корня репозитория после установки `torch`, `torchvision`, `pillow`, `numpy`, `scikit-learn`:

```powershell
.\.venv\Scripts\python.exe -m models.scripts.train_image_detector `
  --train-dir D:\datasets\image-detector\train `
  --test-dir D:\datasets\image-detector\test `
  --checkpoint .\models\checkpoints\ai_image_detector_mobilenet_v3_small.pth
```

Linux/macOS:

```bash
.venv/bin/python -m models.scripts.train_image_detector \
  --train-dir /data/image-detector/train \
  --test-dir /data/image-detector/test \
  --checkpoint models/checkpoints/ai_image_detector_mobilenet_v3_small.pth
```

Параметры `--batch-size`, `--epochs`, `--num-workers`, `--seed`, `--validation-fraction` и learning rates доступны через `--help`.

## Связь с inference

После обучения checkpoint можно проверить так:

```python
from inference.image_analyzer import ImageDetector

detector = ImageDetector(
    "models/checkpoints/ai_image_detector_mobilenet_v3_small.pth",
    architecture="mobilenet_v3_small",
)
```
