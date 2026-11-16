"""Typed configuration for image-detector training."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainingConfig:
    train_dir: Path
    test_dir: Path
    checkpoint_path: Path = Path("models/checkpoints/ai_image_detector_mobilenet_v3_small.pth")
    image_size: int = 224
    batch_size: int = 64
    epochs: int = 8
    validation_fraction: float = 0.10
    seed: int = 42
    early_stopping_patience: int = 2
    classifier_lr: float = 1e-3
    finetune_lr: float = 1e-4
    weight_decay: float = 1e-4
    num_workers: int = 0
    architecture: str = "mobilenet_v3_small"

    @property
    def report_dir(self) -> Path:
        return self.checkpoint_path.parent.parent / "reports" / "image_detector"
