"""Shared artifact-result constructors used by extractors and analyzers."""

from typing import Any


def artifact_error(
    artifact_id: str,
    artifact_type: str,
    error: Exception | str,
    *,
    source: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": artifact_id,
        "type": artifact_type,
        "status": "error",
        "ruling": {"label": "not_analyzed", "score": None},
        "error": str(error),
    }
    if source is not None:
        result["source"] = source
    return result


def artifact_skipped(
    artifact_id: str,
    artifact_type: str,
    reason: str,
    *,
    source: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": artifact_id,
        "type": artifact_type,
        "status": "skipped",
        "ruling": {"label": "not_analyzed", "score": None},
        "reason": reason,
    }
    if source is not None:
        result["source"] = source
    return result
