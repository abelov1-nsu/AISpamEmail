"""Checkpoint format shared with inference.ImageDetector."""

from pathlib import Path
import torch


def save_checkpoint(model, config, epoch: int, metrics: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model_state_dict": model.state_dict(),
        "architecture": config.architecture,
        "epoch": epoch,
        "validation_accuracy": metrics["accuracy"],
        "validation_precision": metrics["precision"],
        "validation_recall": metrics["recall"],
        "validation_f1": metrics["f1"],
        "validation_auc": metrics["auc"],
        "image_size": config.image_size,
        "class_mapping": {"REAL": 0, "FAKE": 1},
    }, path)
