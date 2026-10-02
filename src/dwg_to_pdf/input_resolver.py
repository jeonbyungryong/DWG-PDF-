from pathlib import Path

from .errors import AppError


def _is_reparse_point(path: Path) -> bool:
    """Reject link-like filesystem entries before resolving them."""

    if path.is_symlink():
        return True
    stat = path.stat(follow_symlinks=False)
    attributes = getattr(stat, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def resolve_inputs(paths: list[Path]) -> tuple[Path, ...]:
    """Resolve explicit DWGs and direct folder children in deterministic order."""

    resolved: dict[str, Path] = {}
    try:
        for requested in paths:
            path = Path(requested)
            if _is_reparse_point(path):
                raise AppError("E100", "DWG input selection cannot be a symbolic link or reparse point", path)
            candidates = path.iterdir() if path.is_dir() else (path,)
            for candidate in candidates:
                if _is_reparse_point(candidate):
                    raise AppError(
                        "E100",
                        "DWG input selection cannot contain a symbolic link or reparse point",
                        candidate,
                    )
                if candidate.is_file() and candidate.suffix.casefold() == ".dwg":
                    absolute = candidate.resolve(strict=True)
                    resolved.setdefault(str(absolute).casefold(), absolute)
    except AppError:
        raise
    except (OSError, RuntimeError) as exc:
        raise AppError("E100", "could not resolve DWG input selection") from exc
    if not resolved:
        raise AppError("E100", "no valid DWG inputs were selected")
    return tuple(sorted(resolved.values(), key=lambda path: str(path).casefold()))
