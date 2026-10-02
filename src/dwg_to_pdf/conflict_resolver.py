from pathlib import Path
import sys
from typing import Literal

from .errors import AppError

ConflictPolicy = Literal["ask", "overwrite", "copy", "skip"]
MAX_COPY_NAME_ATTEMPTS = 1_000


def _exists(path: Path) -> bool:
    return path.exists()


def _prompt_conflict(path: Path) -> str:
    print(
        f"PDF already exists: {path}. Choose overwrite, copy, or skip: ",
        file=sys.stderr,
        flush=True,
    )
    return input()


def next_copy_name(path: Path) -> Path:
    """Return the first unused Korean copy-suffix name without creating it."""

    requested = Path(path)
    try:
        for index in range(1, MAX_COPY_NAME_ATTEMPTS + 1):
            suffix = "" if index == 1 else f" {index}"
            candidate = requested.with_name(f"{requested.stem} - 복사본{suffix}{requested.suffix}")
            if not _exists(candidate):
                return candidate
    except OSError as exc:
        raise AppError("E500", "could not inspect existing PDF output", requested) from exc
    raise AppError("E500", "copy output name attempts exhausted", requested)


def resolve_collision(path: Path, policy: ConflictPolicy) -> Path:
    """Select a safe final path; skip and ask never overwrite an existing PDF."""

    requested = Path(path)
    if policy not in ("ask", "overwrite", "copy", "skip"):
        raise AppError("E500", "invalid PDF conflict policy", requested)
    try:
        exists = _exists(requested)
    except OSError as exc:
        raise AppError("E500", "could not inspect existing PDF output", requested) from exc
    if not exists or policy == "overwrite":
        return requested
    if policy == "copy":
        return next_copy_name(requested)
    if policy == "ask":
        try:
            response = _prompt_conflict(requested).strip().casefold()
        except (EOFError, OSError, RuntimeError, TypeError, ValueError):
            response = "skip"
        if response == "overwrite":
            return requested
        if response == "copy":
            return next_copy_name(requested)
    raise AppError("E500", "existing PDF output was not replaced", requested)
