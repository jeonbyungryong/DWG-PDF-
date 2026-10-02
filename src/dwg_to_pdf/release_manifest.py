"""Strict opt-in manifest for real-DWG release regression runs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .errors import AppError
from .templates.scale_universe import APPROVED_SCALE_KEY_SET


@dataclass(frozen=True)
class ActualDrawingCase:
    source: Path
    expected_scale: str
    label: str | None = None


def _read_payload(path: Path) -> list[Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AppError("E001", f"invalid actual drawing manifest: {exc}", path) from exc
    if not isinstance(payload, list):
        raise AppError("E001", "invalid actual drawing manifest: root must be an array", path)
    if len(payload) < 6:
        raise AppError("E001", "invalid actual drawing manifest: at least six cases are required", path)
    return payload


def _parse_case(manifest: Path, value: Any) -> ActualDrawingCase:
    if not isinstance(value, dict):
        raise AppError("E001", "invalid actual drawing manifest: each case must be an object", manifest)
    fields = set(value)
    if fields - {"source", "expected_scale", "label"}:
        raise AppError("E001", "invalid actual drawing manifest: unexpected case field", manifest)
    if {"source", "expected_scale"} - fields:
        raise AppError("E001", "invalid actual drawing manifest: source and expected_scale are required", manifest)
    source_value = value["source"]
    scale = value["expected_scale"]
    label = value.get("label")
    if not isinstance(source_value, str) or not isinstance(scale, str):
        raise AppError("E001", "invalid actual drawing manifest: source and expected_scale must be strings", manifest)
    if label is not None and not isinstance(label, str):
        raise AppError("E001", "invalid actual drawing manifest: label must be a string", manifest)
    source = Path(source_value)
    if not source.is_absolute():
        raise AppError("E001", "invalid actual drawing manifest: source must be absolute", manifest)
    if source.suffix.casefold() != ".dwg":
        raise AppError("E001", "invalid actual drawing manifest: source must be a DWG", manifest)
    try:
        source = source.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise AppError("E001", "invalid actual drawing manifest: source is missing", manifest) from exc
    if not source.is_file():
        raise AppError("E001", "invalid actual drawing manifest: source must be a file", manifest)
    if scale not in APPROVED_SCALE_KEY_SET:
        raise AppError("E001", "invalid actual drawing manifest: unsupported expected_scale", manifest)
    return ActualDrawingCase(source, scale, label)


def load_actual_cases(path: Path) -> tuple[ActualDrawingCase, ...]:
    """Read six-or-more existing DWGs with fail-closed exact case fields."""

    manifest = Path(path)
    cases = tuple(_parse_case(manifest, item) for item in _read_payload(manifest))
    seen: set[str] = set()
    for case in cases:
        key = str(case.source).casefold()
        if key in seen:
            raise AppError("E001", "invalid actual drawing manifest: duplicate source", manifest)
        seen.add(key)
    return cases
