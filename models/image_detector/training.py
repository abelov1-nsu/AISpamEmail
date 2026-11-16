"""High-level training lifecycle and best-checkpoint selection."""

import time
from typing import Any

import torch
from torch import nn

from .checkpointing import save_checkpoint
from .config import TrainingConfig
from .data import build_datasets, create_loader
from .evaluation import evaluate, train_one_epoch
from .model import create_model, freeze_backbone, unfreeze_all
from .reproducibility import configure_runtime, get_device


def train(config: TrainingConfig) -> dict[str, Any]:
    """Train MobileNet and return the final held-out test metrics."""
    if not config.train_dir.is_dir() or not config.test_dir.is_dir():
        raise FileNotFoundError("--train-dir and --test-dir must be existing directories")
    configure_runtime(config.seed)
    device = get_device()
    train_dataset, validation_dataset, test_dataset, _, _ = build_datasets(config)
    if not train_dataset or not validation_dataset or not test_dataset:
        raise ValueError("Train, validation, and test splits must all contain at least one image")
    train_loader = create_loader(train_dataset, config, shuffle=True, device=device)
    validation_loader = create_loader(validation_dataset, config, shuffle=False, device=device)
    test_loader = create_loader(test_dataset, config, shuffle=False, device=device)
    model = create_model(config.architecture).to(device)
    criterion = nn.BCEWithLogitsLoss()
    freeze_backbone(model)
    optimizer = torch.optim.AdamW(filter(lambda item: item.requires_grad, model.parameters()), lr=config.classifier_lr, weight_decay=config.weight_decay)
    best_f1, best_epoch, stale_epochs = -1.0, 0, 0
    history = []
    started_at = time.time()
    for epoch in range(1, config.epochs + 1):
        if epoch == 2:
            unfreeze_all(model)
            optimizer = torch.optim.AdamW(model.parameters(), lr=config.finetune_lr, weight_decay=config.weight_decay)
        train_metrics = train_one_epoch(model, train_loader, criterion, optimizer, device)
        validation_metrics = evaluate(model, validation_loader, criterion, device)
        history.append({"epoch": epoch, "train": train_metrics, "validation": {key: value for key, value in validation_metrics.items() if key not in {"labels", "probabilities", "predictions"}}})
        print(f"Epoch {epoch}/{config.epochs}: train_loss={train_metrics['loss']:.4f}; validation_f1={validation_metrics['f1']:.4f}")
        if validation_metrics["f1"] > best_f1:
            best_f1, best_epoch, stale_epochs = validation_metrics["f1"], epoch, 0
            save_checkpoint(model, config, epoch, validation_metrics, config.checkpoint_path)
        else:
            stale_epochs += 1
            if stale_epochs >= config.early_stopping_patience:
                break
    checkpoint = torch.load(config.checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_metrics = evaluate(model, test_loader, criterion, device)
    return {
        "device": str(device), "best_epoch": best_epoch, "best_validation_f1": best_f1,
        "elapsed_seconds": time.time() - started_at,
        "test": {key: value for key, value in test_metrics.items() if key not in {"labels", "probabilities", "predictions"}},
        "history": history,
    }
