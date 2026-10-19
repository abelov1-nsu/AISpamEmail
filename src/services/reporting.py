"""Serialization helpers for analysis results and reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_json(data: Any, path: Path) -> None:
    """Write JSON data, creating the destination directory if necessary."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as output_file:
        json.dump(data, output_file, indent=2, ensure_ascii=False)


__all__ = ["save_json"]
