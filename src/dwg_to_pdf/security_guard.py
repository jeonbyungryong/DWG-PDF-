from __future__ import annotations

import ast
import os
from pathlib import Path

from .errors import AppError


_BANNED_TOP_LEVEL_MODULES = frozenset({"requests", "httpx", "aiohttp", "socket", "urllib"})


def _security_error(message: str, path: Path | None = None) -> AppError:
    return AppError("E214", message, path)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _python_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    def fail_on_walk_error(error: OSError) -> None:
        raise error

    for directory, directories, names in os.walk(root, followlinks=False, onerror=fail_on_walk_error):
        current = Path(directory)
        directories[:] = sorted(
            (
                name
                for name in directories
                if not (current / name).is_symlink()
                and _is_within((current / name).resolve(), root)
            ),
            key=str.casefold,
        )
        for name in sorted(names, key=str.casefold):
            path = current / name
            if path.suffix != ".py" or path.is_symlink():
                continue
            if not _is_within(path.resolve(), root):
                continue
            files.append(path)
    return tuple(sorted(files, key=lambda path: path.as_posix().casefold()))


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _open_source(path: Path):
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    if no_follow:
        descriptor = os.open(path, os.O_RDONLY | no_follow)
        return os.fdopen(descriptor, "r", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def _read_audited_source(path: Path, root: Path) -> str:
    if path.is_symlink() or not _is_within(path.resolve(strict=True), root):
        raise _security_error("source path escaped audit root", path)
    before = path.stat()
    with _open_source(path) as handle:
        opened = os.fstat(handle.fileno())
        if not _same_file(before, opened):
            raise _security_error("source file changed before audit read", path)
        source = handle.read()
        after_read = path.stat()
    if (
        path.is_symlink()
        or not _is_within(path.resolve(strict=True), root)
        or not _same_file(before, after_read)
    ):
        raise _security_error("source file changed during audit read", path)
    return source


def _banned_module(node: ast.Import | ast.ImportFrom) -> str | None:
    if isinstance(node, ast.Import):
        names = (alias.name for alias in node.names)
    else:
        names = (node.module or "",)
    for name in names:
        top_level = name.split(".", maxsplit=1)[0]
        if top_level in _BANNED_TOP_LEVEL_MODULES:
            return name
    return None


def audit_source_tree(package_root: Path) -> tuple[Path, ...]:
    """Audit local Python source imports without traversing outside the package."""
    supplied_root = Path(package_root)
    try:
        if supplied_root.is_symlink() or not supplied_root.is_dir():
            raise _security_error("invalid source audit root", supplied_root)
        root = supplied_root.resolve(strict=True)
        files = _python_files(root)
        for path in files:
            source = _read_audited_source(path, root)
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = _banned_module(node)
                    if module is not None:
                        raise _security_error(f"network import is prohibited: {module}", path)
        return files
    except AppError:
        raise
    except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
        raise _security_error(f"source audit failed: {exc}", supplied_root) from exc
