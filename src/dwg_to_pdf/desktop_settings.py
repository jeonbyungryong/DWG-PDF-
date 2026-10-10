"""Remember successful AutoCAD desktop settings for the current Windows user."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

from .cad.selection import CadCandidate
from .configuration import load_config
from .errors import AppError


def _settings_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return root / "DWG-to-PDF" / "autocad-settings.json"


def _installation_key(candidate: CadCandidate) -> str:
    return json.dumps([
        candidate.prog_id.casefold(), candidate.clsid.casefold(),
        str(candidate.executable).casefold(), candidate.reported_version,
        candidate.launch_arguments,
    ], ensure_ascii=False)


def _read_settings(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (isinstance(data, dict) and type(data.get("version")) is int
                and data["version"] == 1 and isinstance(data.get("installations"), dict)):
            return data
    except (OSError, ValueError):
        pass
    return {"version": 1, "installations": {}}


def _config_record(path: Path) -> dict:
    path = path.resolve(strict=True)
    config = load_config(path)
    if config.cad_provider != "autocad":
        raise ValueError("only AutoCAD settings can be remembered")
    return {
        "config_path": str(path),
        "config_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "pc3_sha256": (hashlib.sha256(config.autocad_pc3_path.read_bytes()).hexdigest()
                       if config.autocad_pc3_path is not None else None),
    }


def remembered_autocad_config(candidate: CadCandidate) -> str | None:
    entry = _read_settings(_settings_path())["installations"].get(_installation_key(candidate))
    try:
        if isinstance(entry, dict) and entry == _config_record(Path(entry["config_path"])):
            return entry["config_path"]
    except (AppError, OSError, ValueError, KeyError, TypeError):
        pass
    return None


def autocad_config_snapshot(config_path: str) -> dict | None:
    try:
        return _config_record(Path(config_path))
    except (AppError, OSError, ValueError):
        return None


def remember_autocad_config(candidate: CadCandidate, config_path: str, expected_record: dict | None) -> None:
    temporary = None
    try:
        record = _config_record(Path(config_path))
        if record != expected_record:
            raise ValueError("settings changed during conversion")
        path = _settings_path()
        data = _read_settings(path)
        data["installations"][_installation_key(candidate)] = record
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
        temporary.replace(path)
    except (AppError, OSError, ValueError):
        print("설정 기억에 실패했습니다. 다음 실행에서 설정을 자동 준비합니다.", file=sys.stderr)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
