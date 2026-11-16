"""MobileNet architecture and transfer-learning controls."""

import torch
from torch import nn
from torchvision import models
from torchvision.models import MobileNet_V3_Small_Weights


def create_model(architecture: str = "mobilenet_v3_small") -> nn.Module:
    if architecture != "mobilenet_v3_small":
        raise ValueError(f"Unsupported architecture: {architecture}")
    model = models.mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, 1)
    return model


def freeze_backbone(model: nn.Module) -> None:
    for parameter in model.features.parameters():
        parameter.requires_grad = False
    for parameter in model.classifier.parameters():
        parameter.requires_grad = True


def unfreeze_all(model: nn.Module) -> None:
    for parameter in model.parameters():
        parameter.requires_grad = True
