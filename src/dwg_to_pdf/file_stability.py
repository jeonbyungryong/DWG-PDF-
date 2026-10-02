from __future__ import annotations

import math
from pathlib import Path
import time

from .errors import AppError


def _stat(path: Path):
    return path.stat()


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def require_stable(path: Path, interval_sec: float = 1.0) -> None:
    """Hold a DWG closed unless consecutive size and mtime snapshots agree."""

    if isinstance(interval_sec, bool) or not isinstance(interval_sec, (int, float)):
        raise ValueError("interval_sec must be numeric")
    if not math.isfinite(interval_sec) or interval_sec < 0:
        raise ValueError("interval_sec must be finite and non-negative")
    requested = Path(path)
    try:
        first = _stat(requested)
        _sleep(float(interval_sec))
        second = _stat(requested)
        if (first.st_size, first.st_mtime_ns) != (second.st_size, second.st_mtime_ns):
            raise AppError("E215", "input DWG is still changing", requested)
    except AppError:
        raise
    except (OSError, RuntimeError, ValueError, AttributeError, OverflowError) as exc:
        raise AppError("E215", "could not verify input DWG stability", requested) from exc
