"""ImageFolder datasets, label mapping and loaders."""

import random
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset, Subset
from torchvision import datasets, transforms

from .config import TrainingConfig


def convert_label(imagefolder_label: int, class_to_idx: dict[str, int]) -> int:
    class_name = {value: key for key, value in class_to_idx.items()}[imagefolder_label]
    if class_name == "FAKE":
        return 1
    if class_name == "REAL":
        return 0
    raise RuntimeError(f"Unexpected class name: {class_name}")


class RemappedSubset(Dataset):
    def __init__(self, dataset: Dataset, class_to_idx: dict[str, int]):
        self.dataset = dataset
        self.class_to_idx = class_to_idx

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, index):
        image, label = self.dataset[index]
        return image, torch.tensor(convert_label(label, self.class_to_idx), dtype=torch.float32)


def build_datasets(config: TrainingConfig):
    train_transform = transforms.Compose([
        transforms.Resize((config.image_size, config.image_size)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])
    eval_transform = transforms.Compose([
        transforms.Resize((config.image_size, config.image_size)),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])
    train_aug = datasets.ImageFolder(config.train_dir, transform=train_transform)
    train_eval = datasets.ImageFolder(config.train_dir, transform=eval_transform)
    test = datasets.ImageFolder(config.test_dir, transform=eval_transform)
    expected = {"FAKE", "REAL"}
    if set(train_aug.classes) != expected or set(test.classes) != expected:
        raise RuntimeError("Training and test directories must contain exactly FAKE and REAL folders")
    indices = list(range(len(train_aug)))
    random.Random(config.seed).shuffle(indices)
    validation_size = int(len(indices) * config.validation_fraction)
    validation_indices, train_indices = indices[:validation_size], indices[validation_size:]
    return (
        RemappedSubset(Subset(train_aug, train_indices), train_aug.class_to_idx),
        RemappedSubset(Subset(train_eval, validation_indices), train_aug.class_to_idx),
        RemappedSubset(test, test.class_to_idx),
        train_aug.class_to_idx,
        test.class_to_idx,
    )


def create_loader(dataset: Dataset, config: TrainingConfig, *, shuffle: bool, device: torch.device) -> DataLoader:
    return DataLoader(dataset, batch_size=config.batch_size, shuffle=shuffle, num_workers=config.num_workers, pin_memory=device.type == "cuda")
