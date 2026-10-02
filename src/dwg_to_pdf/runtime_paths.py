"""Resolve bundled resources without changing source-mode defaults."""

from __future__ import annotations

from pathlib import Path
import sys


def _bundle_root() -> Path | None:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return None


def default_config_path() -> Path:
    """Return the validation config bundled by PyInstaller, or source default."""
    root = _bundle_root()
    return root / "config.toml" if root is not None else Path("config.toml")


def default_profiles_path() -> Path:
    """Return bundled profiles, or the established cwd-relative source default."""
    root = _bundle_root()
    return root / "template_profiles" if root is not None else Path("template_profiles")


def prefer_explicit(explicit: Path | None, default: Path) -> Path:
    return default if explicit is None else explicit
