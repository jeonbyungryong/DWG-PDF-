from __future__ import annotations

import winreg

from ..errors import AppError


def require_registered_prog_id(prog_id: str) -> str:
    """Return a non-empty registered ProgID, or fail without starting COM."""

    candidate = str(prog_id).strip()
    if not candidate or "\\" in candidate or "/" in candidate:
        raise AppError("E202", "GstarCAD COM ProgID is invalid")
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{candidate}\CLSID") as key:
            clsid, _ = winreg.QueryValueEx(key, None)
    except OSError as exc:
        raise AppError("E202", f"GstarCAD COM ProgID is not registered: {candidate}") from exc
    if not str(clsid).strip():
        raise AppError("E202", f"GstarCAD COM ProgID has no CLSID: {candidate}")
    return candidate
