from __future__ import annotations

import re
from pathlib import Path

from .errors import AppError


_REQUIRED = frozenset({"pywin32", "jsonschema", "pypdf", "pypdfium2", "pillow"})
_REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[^]]+\])?==([^\s\\]+)(?:\s+\\)?\s*(?:#.*)?$")
_HASH = re.compile(r"^\s*--hash=sha256:([0-9a-fA-F]{64})(?:\s+\\)?\s*$")
_HASH_PREFIX = re.compile(r"^\s*--hash=")


def _canonicalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _error(message: str, path: Path, cause: BaseException | None = None) -> AppError:
    error = AppError("E214", f"dependency lock audit failed: {message}", path)
    if cause is not None:
        raise error from cause
    return error


def _continues(line: str) -> bool:
    return line.rstrip().endswith("\\")


def require_hashed_lock(path: Path) -> None:
    """Ensure each required direct runtime distribution has its own SHA-256 hash."""
    lock_path = Path(path)
    try:
        lines = lock_path.read_text(encoding="utf-8").splitlines()
        blocks: dict[str, list[str]] = {}
        current: str | None = None
        expecting_hash = False
        for line in lines:
            if expecting_hash:
                match = _HASH.match(line)
                if match is None:
                    raise _error("expected a continued SHA-256 hash block", lock_path)
                if current is not None:
                    blocks[current].append(match.group(1).lower())
                expecting_hash = _continues(line)
                if not expecting_hash:
                    current = None
                continue
            if _HASH_PREFIX.match(line):
                raise _error("orphan or unexpected hash block", lock_path)
            if line and not line[0].isspace() and not line.startswith("#"):
                current = None
            requirement = _REQUIREMENT.match(line)
            if requirement is not None:
                name = _canonicalize(requirement.group(1))
                current = name if name in _REQUIRED else None
                if name in _REQUIRED:
                    if name in blocks:
                        raise _error(f"duplicate required entry: {name}", lock_path)
                    blocks[name] = []
                expecting_hash = _continues(line)
                continue
        if expecting_hash:
            raise _error("required hash continuation ended unexpectedly", lock_path)
        missing = sorted(_REQUIRED.difference(blocks))
        if missing:
            raise _error(f"missing pinned required entries: {', '.join(missing)}", lock_path)
        unhashed = sorted(name for name in _REQUIRED if not blocks[name])
        if unhashed:
            raise _error(f"missing SHA-256 hash in required blocks: {', '.join(unhashed)}", lock_path)
    except AppError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise _error(str(exc), lock_path, exc)
