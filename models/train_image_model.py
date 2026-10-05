"""
train_image_detector.py

Train a binary AI-generated-vs-real image detector.

Expected dataset:

    data/
        images/
            train/
                fake/
                    image1.jpg
                    image2.jpg
                    ...
                real/
                    image1.jpg
                    image2.jpg
                    ...
            test/
                fake/
                    ...
                real/
                    ...

The script:
    - Uses ImageNet-pretrained MobileNetV3-Small.
    - Replaces the classifier with one binary logit.
    - Creates a validation split from the training data.
    - Trains on the GTX 1070 when CUDA is available.
    - Evaluates on the held-out test set.
    - Saves a checkpoint compatible with ImageDetector.
    - Reports accuracy, precision, recall, F1 and confusion matrix.
    - Saves the best validation checkpoint.

Install dependencies:

    pip install torch torchvision pillow scikit-learn

For CUDA-enabled PyTorch, install the appropriate PyTorch build for
your system from:
    https://pytorch.org/get-started/locally/

Then run:

    python train_image_detector.py
"""

from __future__ import annotations

import os
import random
import time
from pathlib import Path

import numpy as np
import torch
from PIL import ImageFile
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from torch import nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, models, transforms
from torchvision.models import MobileNet_V3_Small_Weights


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

TRAIN_DIR = PROJECT_ROOT / "data" / "images" / "train"
TEST_DIR = PROJECT_ROOT / "data" / "images" / "test"

MODEL_DIR = PROJECT_ROOT / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_PATH = MODEL_DIR / "ai_image_detector_mobilenet_v3_small.pth"

# Image size expected by the inference code.
IMAGE_SIZE = 224

# GTX 1070 should comfortably handle this for MobileNetV3-Small.
BATCH_SIZE = 64

# Number of complete passes through the training data.
NUM_EPOCHS = 8

# Fraction of training data reserved for validation.
VALIDATION_FRACTION = 0.10

# Reproducibility.
SEED = 42

# Number of epochs without validation improvement before stopping.
EARLY_STOPPING_PATIENCE = 2

# Learning rates.
#
# The classifier is trained first with a larger LR.
# Then the whole network is fine-tuned with a smaller LR.
CLASSIFIER_LR = 1e-3
FINETUNE_LR = 1e-4

# Weight decay helps reduce overfitting.
WEIGHT_DECAY = 1e-4

# DataLoader workers.
#
# If Windows gives worker-related problems, set this to 0.
NUM_WORKERS = min(8, os.cpu_count() or 1)

# Use pretrained ImageNet normalization.
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


# ============================================================
# Setup
# ============================================================

ImageFile.LOAD_TRUNCATED_IMAGES = True


def set_seed(seed: int) -> None:
    """Make the training split and initialization reproducible."""

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    # These make results more reproducible, at the cost of some speed.
    torch.backends.cudnn.deterministic = False
    torch.backends.cudnn.benchmark = True


def print_header() -> None:
    print("=" * 70)
    print("AI IMAGE DETECTOR TRAINING")
    print("=" * 70)
    print()

    print(f"Project root:       {PROJECT_ROOT}")
    print(f"Training directory: {TRAIN_DIR}")
    print(f"Test directory:     {TEST_DIR}")
    print(f"Checkpoint:         {CHECKPOINT_PATH}")
    print()


def get_device() -> torch.device:
    if torch.cuda.is_available():
        device = torch.device("cuda")

        print("CUDA is available.")
        print(f"GPU: {torch.cuda.get_device_name(0)}")

        props = torch.cuda.get_device_properties(0)
        print(
            f"VRAM: {props.total_memory / (1024 ** 3):.1f} GB"
        )

        print(
            f"CUDA version reported by PyTorch: "
            f"{torch.version.cuda}"
        )

        return device

    print("WARNING: CUDA is NOT available.")
    print("Training will run on CPU.")
    print()
    return torch.device("cpu")


# ============================================================
# Dataset
# ============================================================

def build_datasets():
    """
    Build training/validation/test datasets.

    We deliberately use separate transforms for training and evaluation.
    """

    train_transform = transforms.Compose(
        [
            transforms.RandomResizedCrop(
                IMAGE_SIZE,
                scale=(0.80, 1.0),
            ),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ColorJitter(
                brightness=0.10,
                contrast=0.10,
                saturation=0.05,
                hue=0.02,
            ),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=IMAGENET_MEAN,
                std=IMAGENET_STD,
            ),
        ]
    )

    eval_transform = transforms.Compose(
        [
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=IMAGENET_MEAN,
                std=IMAGENET_STD,
            ),
        ]
    )

    # We create two copies of the training dataset:
    #
    # one with augmentation for training
    # one without augmentation for validation
    #
    # Both contain exactly the same underlying files.
    full_train_augmented = datasets.ImageFolder(
        TRAIN_DIR,
        transform=train_transform,
    )

    full_train_eval = datasets.ImageFolder(
        TRAIN_DIR,
        transform=eval_transform,
    )

    test_dataset = datasets.ImageFolder(
        TEST_DIR,
        transform=eval_transform,
    )

    print("Detected classes:")
    print(f"  Training: {full_train_augmented.class_to_idx}")
    print(f"  Test:     {test_dataset.class_to_idx}")
    print()

    # We explicitly require the expected folders.
    required_classes = {"fake", "real"}

    if set(full_train_augmented.classes) != required_classes:
        raise RuntimeError(
            "Training dataset must contain exactly these class folders: "
            "'fake' and 'real'. "
            f"Found: {full_train_augmented.classes}"
        )

    if set(test_dataset.classes) != required_classes:
        raise RuntimeError(
            "Test dataset must contain exactly these class folders: "
            "'fake' and 'real'. "
            f"Found: {test_dataset.classes}"
        )

    # ImageFolder normally assigns alphabetic indices:
    #
    # fake -> 0
    # real -> 1
    #
    # But our detector wants:
    #
    # real -> 0
    # fake -> 1
    #
    # We will explicitly remap labels later rather than relying on
    # ImageFolder's alphabetical ordering.

    total = len(full_train_augmented)

    indices = list(range(total))

    rng = random.Random(SEED)
    rng.shuffle(indices)

    validation_size = int(total * VALIDATION_FRACTION)

    validation_indices = indices[:validation_size]
    train_indices = indices[validation_size:]

    train_dataset = Subset(
        full_train_augmented,
        train_indices,
    )

    validation_dataset = Subset(
        full_train_eval,
        validation_indices,
    )

    print(f"Total training images:    {total:,}")
    print(f"Actual training images:   {len(train_dataset):,}")
    print(f"Validation images:        {len(validation_dataset):,}")
    print(f"Test images:              {len(test_dataset):,}")
    print()

    return (
        train_dataset,
        validation_dataset,
        test_dataset,
        full_train_augmented.class_to_idx,
        test_dataset.class_to_idx,
    )


# ============================================================
# Label handling
# ============================================================

def convert_label(imagefolder_label: int, class_to_idx: dict[str, int]) -> int:
    """
    Convert ImageFolder's label into our detector convention.

    Detector convention:

        0 = real
        1 = fake / AI
    """

    idx_to_class = {
        value: key
        for key, value in class_to_idx.items()
    }

    class_name = idx_to_class[imagefolder_label]

    if class_name == "fake":
        return 1

    if class_name == "real":
        return 0

    raise RuntimeError(
        f"Unexpected class name: {class_name}"
    )


class RemappedSubset(torch.utils.data.Dataset):
    """Dataset wrapper that changes fake/real labels to 1/0."""

    def __init__(
        self,
        dataset,
        class_to_idx: dict[str, int],
    ):
        self.dataset = dataset
        self.class_to_idx = class_to_idx

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, index):
        image, label = self.dataset[index]

        label = convert_label(
            label,
            self.class_to_idx,
        )

        return image, torch.tensor(
            label,
            dtype=torch.float32,
        )


# ============================================================
# Model
# ============================================================

def create_model() -> nn.Module:
    """
    Create ImageNet-pretrained MobileNetV3-Small.

    The final ImageNet classifier is replaced with one binary logit.
    """

    weights = MobileNet_V3_Small_Weights.DEFAULT

    print("Loading ImageNet-pretrained MobileNetV3-Small...")

    model = models.mobilenet_v3_small(
        weights=weights
    )

    input_features = model.classifier[-1].in_features

    model.classifier[-1] = nn.Linear(
        input_features,
        1,
    )

    return model


def freeze_backbone(model: nn.Module) -> None:
    """
    Freeze everything except the classifier.

    This gives the new binary classifier a chance to learn before
    the pretrained feature extractor is fine-tuned.
    """

    for parameter in model.features.parameters():
        parameter.requires_grad = False

    for parameter in model.classifier.parameters():
        parameter.requires_grad = True


def unfreeze_all(model: nn.Module) -> None:
    """Allow the entire network to be fine-tuned."""

    for parameter in model.parameters():
        parameter.requires_grad = True


# ============================================================
# Training / evaluation
# ============================================================

def create_loader(
    dataset,
    shuffle: bool,
    device: torch.device,
):
    kwargs = {
        "batch_size": BATCH_SIZE,
        "shuffle": shuffle,
        "num_workers": NUM_WORKERS,
        "pin_memory": device.type == "cuda",
    }

    # Persistent workers avoid repeatedly creating worker processes
    # between epochs when multiprocessing is enabled.
    if NUM_WORKERS > 0:
        kwargs["persistent_workers"] = True

    return DataLoader(
        dataset,
        **kwargs,
    )


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion,
    optimizer,
    scaler,
    device: torch.device,
) -> tuple[float, float]:

    model.train()

    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in loader:
        images = images.to(
            device,
            non_blocking=True,
        )

        labels = labels.to(
            device,
            non_blocking=True,
        ).unsqueeze(1)

        optimizer.zero_grad(
            set_to_none=True
        )

        if device.type == "cuda":
            with torch.cuda.amp.autocast():
                logits = model(images)
                loss = criterion(
                    logits,
                    labels,
                )

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

        else:
            logits = model(images)

            loss = criterion(
                logits,
                labels,
            )

            loss.backward()
            optimizer.step()

        running_loss += (
            loss.item() * images.size(0)
        )

        predictions = (
            torch.sigmoid(logits) >= 0.5
        )

        correct += (
            (predictions == labels.bool())
            .sum()
            .item()
        )

        total += images.size(0)

    average_loss = running_loss / total
    accuracy = correct / total

    return average_loss, accuracy


@torch.inference_mode()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion,
    device: torch.device,
):
    model.eval()

    running_loss = 0.0
    total = 0

    all_probabilities = []
    all_labels = []

    for images, labels in loader:
        images = images.to(
            device,
            non_blocking=True,
        )

        labels = labels.to(
            device,
            non_blocking=True,
        ).unsqueeze(1)

        if device.type == "cuda":
            with torch.cuda.amp.autocast():
                logits = model(images)
                loss = criterion(
                    logits,
                    labels,
                )
        else:
            logits = model(images)

            loss = criterion(
                logits,
                labels,
            )

        probabilities = torch.sigmoid(
            logits
        ).squeeze(1)

        running_loss += (
            loss.item() * images.size(0)
        )

        total += images.size(0)

        all_probabilities.extend(
            probabilities.detach()
            .cpu()
            .numpy()
            .tolist()
        )

        all_labels.extend(
            labels.squeeze(1)
            .detach()
            .cpu()
            .numpy()
            .astype(int)
            .tolist()
        )

    average_loss = running_loss / total

    probabilities = np.array(
        all_probabilities
    )

    labels = np.array(
        all_labels
    )

    predictions = (
        probabilities >= 0.5
    ).astype(int)

    accuracy = accuracy_score(
        labels,
        predictions,
    )

    precision = precision_score(
        labels,
        predictions,
        zero_division=0,
    )

    recall = recall_score(
        labels,
        predictions,
        zero_division=0,
    )

    f1 = f1_score(
        labels,
        predictions,
        zero_division=0,
    )

    try:
        auc = roc_auc_score(
            labels,
            probabilities,
        )
    except ValueError:
        auc = float("nan")

    return {
        "loss": average_loss,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "auc": auc,
        "labels": labels,
        "probabilities": probabilities,
        "predictions": predictions,
    }


# ============================================================
# Checkpoint
# ============================================================

def save_checkpoint(
    model: nn.Module,
    epoch: int,
    validation_metrics: dict,
):
    """
    Save a checkpoint compatible with image_analyzer.py.

    image_analyzer.py accepts:

        checkpoint["model_state_dict"]
    """

    checkpoint = {
        "model_state_dict": model.state_dict(),

        "architecture": "mobilenet_v3_small",

        "epoch": epoch,

        "validation_accuracy": validation_metrics[
            "accuracy"
        ],

        "validation_precision": validation_metrics[
            "precision"
        ],

        "validation_recall": validation_metrics[
            "recall"
        ],

        "validation_f1": validation_metrics[
            "f1"
        ],

        "validation_auc": validation_metrics[
            "auc"
        ],

        "image_size": IMAGE_SIZE,

        "class_mapping": {
            "real": 0,
            "fake": 1,
        },
    }

    torch.save(
        checkpoint,
        CHECKPOINT_PATH,
    )


# ============================================================
# Main
# ============================================================

def main():
    set_seed(SEED)

    print_header()

    # --------------------------------------------------------
    # Validate directories
    # --------------------------------------------------------

    if not TRAIN_DIR.exists():
        raise FileNotFoundError(
            f"Training directory does not exist:\n{TRAIN_DIR}"
        )

    if not TEST_DIR.exists():
        raise FileNotFoundError(
            f"Test directory does not exist:\n{TEST_DIR}"
        )

    # --------------------------------------------------------
    # Device
    # --------------------------------------------------------

    device = get_device()

    print()

    # --------------------------------------------------------
    # Dataset
    # --------------------------------------------------------

    (
        train_dataset_raw,
        validation_dataset_raw,
        test_dataset_raw,
        train_class_to_idx,
        test_class_to_idx,
    ) = build_datasets()

    train_dataset = RemappedSubset(
        train_dataset_raw,
        train_class_to_idx,
    )

    validation_dataset = RemappedSubset(
        validation_dataset_raw,
        train_class_to_idx,
    )

    test_dataset = RemappedSubset(
        test_dataset_raw,
        test_class_to_idx,
    )

    train_loader = create_loader(
        train_dataset,
        shuffle=True,
        device=device,
    )

    validation_loader = create_loader(
        validation_dataset,
        shuffle=False,
        device=device,
    )

    test_loader = create_loader(
        test_dataset,
        shuffle=False,
        device=device,
    )

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    model = create_model()
    model.to(device)

    criterion = nn.BCEWithLogitsLoss()

    scaler = torch.cuda.amp.GradScaler(
        enabled=device.type == "cuda"
    )

    # --------------------------------------------------------
    # Phase 1: classifier training
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PHASE 1: TRAINING CLASSIFIER")
    print("=" * 70)

    freeze_backbone(model)

    optimizer = torch.optim.AdamW(
        filter(
            lambda p: p.requires_grad,
            model.parameters(),
        ),
        lr=CLASSIFIER_LR,
        weight_decay=WEIGHT_DECAY,
    )

    best_validation_f1 = -1.0
    best_epoch = -1
    epochs_without_improvement = 0

    start_time = time.time()

    for epoch in range(NUM_EPOCHS):

        # After the first epoch, fine-tune the entire model.
        if epoch == 1:
            print()
            print(
                "Unfreezing MobileNet backbone for fine-tuning..."
            )

            unfreeze_all(model)

            optimizer = torch.optim.AdamW(
                model.parameters(),
                lr=FINETUNE_LR,
                weight_decay=WEIGHT_DECAY,
            )

        epoch_start = time.time()

        train_loss, train_accuracy = train_one_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            scaler,
            device,
        )

        validation_metrics = evaluate(
            model,
            validation_loader,
            criterion,
            device,
        )

        elapsed = time.time() - epoch_start

        print()
        print("-" * 70)
        print(
            f"Epoch {epoch + 1}/{NUM_EPOCHS} "
            f"({elapsed / 60:.1f} min)"
        )
        print("-" * 70)

        print(
            f"Train loss:       {train_loss:.4f}"
        )

        print(
            f"Train accuracy:   {train_accuracy * 100:.2f}%"
        )

        print(
            f"Validation loss:  "
            f"{validation_metrics['loss']:.4f}"
        )

        print(
            f"Validation acc:   "
            f"{validation_metrics['accuracy'] * 100:.2f}%"
        )

        print(
            f"Validation F1:    "
            f"{validation_metrics['f1'] * 100:.2f}%"
        )

        print(
            f"Validation AUC:   "
            f"{validation_metrics['auc']:.4f}"
        )

        # ----------------------------------------------------
        # Save best model
        # ----------------------------------------------------

        if validation_metrics["f1"] > best_validation_f1:

            best_validation_f1 = validation_metrics[
                "f1"
            ]

            best_epoch = epoch + 1
            epochs_without_improvement = 0

            save_checkpoint(
                model,
                epoch + 1,
                validation_metrics,
            )

            print()
            print(
                "NEW BEST MODEL SAVED:"
            )
            print(
                f"  {CHECKPOINT_PATH}"
            )

        else:
            epochs_without_improvement += 1

            print()
            print(
                "No validation improvement."
            )

        if (
            epochs_without_improvement
            >= EARLY_STOPPING_PATIENCE
        ):
            print()
            print(
                "Early stopping triggered."
            )
            break

    total_training_time = (
        time.time() - start_time
    )

    # --------------------------------------------------------
    # Load best checkpoint
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("LOADING BEST MODEL")
    print("=" * 70)

    checkpoint = torch.load(
        CHECKPOINT_PATH,
        map_location=device,
        weights_only=False,
    )

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    model.to(device)
    model.eval()

    print(
        f"Best epoch: {best_epoch}"
    )

    print(
        f"Best validation F1: "
        f"{best_validation_f1 * 100:.2f}%"
    )

    # --------------------------------------------------------
    # Final test evaluation
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("FINAL TEST SET")
    print("=" * 70)

    test_metrics = evaluate(
        model,
        test_loader,
        criterion,
        device,
    )

    print()
    print(
        f"Test loss:       "
        f"{test_metrics['loss']:.4f}"
    )

    print(
        f"Test accuracy:   "
        f"{test_metrics['accuracy'] * 100:.2f}%"
    )

    print(
        f"Test precision:  "
        f"{test_metrics['precision'] * 100:.2f}%"
    )

    print(
        f"Test recall:     "
        f"{test_metrics['recall'] * 100:.2f}%"
    )

    print(
        f"Test F1:         "
        f"{test_metrics['f1'] * 100:.2f}%"
    )

    print(
        f"Test ROC-AUC:    "
        f"{test_metrics['auc']:.4f}"
    )

    # --------------------------------------------------------
    # Confusion matrix
    # --------------------------------------------------------

    matrix = confusion_matrix(
        test_metrics["labels"],
        test_metrics["predictions"],
    )

    print()
    print("Confusion matrix:")
    print()
    print("                 Predicted")
    print("                 REAL    AI")
    print(
        f"Actual REAL      {matrix[0, 0]:6d} "
        f"{matrix[0, 1]:6d}"
    )
    print(
        f"Actual AI        {matrix[1, 0]:6d} "
        f"{matrix[1, 1]:6d}"
    )

    # --------------------------------------------------------
    # Finished
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)

    print(
        f"Total training time: "
        f"{total_training_time / 3600:.2f} hours"
    )

    print()
    print("Model saved to:")
    print(CHECKPOINT_PATH)

    print()
    print(
        "You can now load it with image_analyzer.py:"
    )

    print()
    print(
        'ImageDetector('
        f'checkpoint="{CHECKPOINT_PATH}", '
        'architecture="mobilenet_v3_small"'
        ')'
    )

    print()
    print(
        "IMPORTANT:"
    )
    print(
        "The test score is only meaningful if the test images "
        "were never used during training or model selection."
    )


if __name__ == "__main__":
    main()