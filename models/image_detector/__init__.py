"""Training components for the binary AI-vs-real image detector."""

from .config import TrainingConfig
from .model import create_model

__all__ = ["TrainingConfig", "create_model"]
