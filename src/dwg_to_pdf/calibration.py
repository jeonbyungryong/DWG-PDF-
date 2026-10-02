from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from .errors import AppError


_FIELDS = frozenset({"threshold", "gap", "false_approvals", "correct_approvals"})


def _error(message: str) -> AppError:
    return AppError("E214", f"invalid calibration candidate: {message}")


def _score(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0 < result <= 1:
        raise _error(f"{field} must be finite and within (0, 1]")
    return result


def _count(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _error(f"{field} must be a non-negative integer")
    return value


def _normalize(candidate: Mapping[str, Any]) -> tuple[float, float, int, int]:
    if set(candidate) != _FIELDS:
        raise _error("fields must be exactly threshold, gap, false_approvals, correct_approvals")
    return (
        _score(candidate["threshold"], "threshold"),
        _score(candidate["gap"], "gap"),
        _count(candidate["false_approvals"], "false_approvals"),
        _count(candidate["correct_approvals"], "correct_approvals"),
    )


def choose_parameters(candidates: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    """Return the strongest candidate that made no false approvals.

    This only selects from labelled evidence; it does not change application
    configuration or enable auto-matching.
    """
    try:
        normalized = [_normalize(candidate) for candidate in candidates]
    except AppError:
        raise
    except (TypeError, KeyError) as exc:
        raise _error("candidate must be a mapping with required fields") from exc

    safe = [candidate for candidate in normalized if candidate[2] == 0]
    if not safe:
        raise _error("no candidate has zero false approvals")
    threshold, gap, _, _ = max(safe, key=lambda item: (item[3], item[1], item[0]))
    return {"threshold": threshold, "gap": gap}
