"""Reproducibility and runtime setup."""

import random
import numpy as np
import torch
from PIL import ImageFile


def configure_runtime(seed: int) -> None:
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = False
    torch.backends.cudnn.benchmark = True


def get_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")
