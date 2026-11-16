"""Training and evaluation loops with binary classification metrics."""

import numpy as np
import torch
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score


def train_one_epoch(model, loader, criterion, optimizer, device):
    model.train(); running_loss = 0.0; correct = 0; total = 0
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device).unsqueeze(1)
        optimizer.zero_grad(set_to_none=True)
        logits = model(images); loss = criterion(logits, labels)
        loss.backward(); optimizer.step()
        running_loss += loss.item() * images.size(0)
        correct += ((torch.sigmoid(logits) >= 0.5) == labels.bool()).sum().item(); total += images.size(0)
    return {"loss": running_loss / total, "accuracy": correct / total}


@torch.inference_mode()
def evaluate(model, loader, criterion, device):
    model.eval(); losses = []; probabilities = []; labels_all = []
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device).unsqueeze(1)
        logits = model(images); losses.append(criterion(logits, labels).item() * images.size(0))
        probabilities.extend(torch.sigmoid(logits).squeeze(1).cpu().numpy().tolist())
        labels_all.extend(labels.squeeze(1).cpu().numpy().astype(int).tolist())
    probabilities = np.array(probabilities); labels = np.array(labels_all); predictions = (probabilities >= 0.5).astype(int)
    try: auc = roc_auc_score(labels, probabilities)
    except ValueError: auc = float("nan")
    return {"loss": sum(losses) / len(labels), "accuracy": accuracy_score(labels, predictions), "precision": precision_score(labels, predictions, zero_division=0), "recall": recall_score(labels, predictions, zero_division=0), "f1": f1_score(labels, predictions, zero_division=0), "auc": auc, "labels": labels, "probabilities": probabilities, "predictions": predictions}
