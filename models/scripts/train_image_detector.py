"""CLI for reproducible AI-image detector training."""

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from models.image_detector.config import TrainingConfig
from models.image_detector.training import train


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a binary FAKE-vs-REAL MobileNetV3 image detector.")
    parser.add_argument("--train-dir", type=Path, required=True)
    parser.add_argument("--test-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, default=Path("models/checkpoints/ai_image_detector_mobilenet_v3_small.pth"))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--num-workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validation-fraction", type=float, default=0.10)
    parser.add_argument("--classifier-lr", type=float, default=1e-3)
    parser.add_argument("--finetune-lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--early-stopping-patience", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = TrainingConfig(**vars(args))
    print(json.dumps({key: str(value) if isinstance(value, Path) else value for key, value in asdict(config).items()}, indent=2))
    result = train(config)
    print(json.dumps(result, indent=2, default=lambda value: value.item() if hasattr(value, "item") else value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
