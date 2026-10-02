"""Read-only ownership proof before any COM mutation; exact-handle cleanup."""
from __future__ import annotations

from contextlib import AbstractContextManager
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Any

import pywintypes  # noqa: F401 - bootstrap pywin32 DLL loading
import win32api
import win32event
import win32process

from ..errors import AppError
from .selection import CadCandidate


def _all_pids() -> frozenset[int]:
    try:
        return frozenset(win32process.EnumProcesses())
    except Exception as exc:
        raise AppError("E201", "could not enumerate process identities") from exc


def _product_pids(candidate: CadCandidate) -> frozenset[int]:
    return provider_pids(candidate.provider)


def provider_pids(provider: str) -> frozenset[int]:
    name = {"gstarcad": "gcad", "autocad": "acad"}[provider]
    command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
               f"Get-Process -Name {name} -ErrorAction SilentlyContinue | ForEach-Object {{ $_.Id }}"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10,
                            check=False, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip():
        return frozenset()
    if result.returncode:
        raise AppError("E201", "CAD process enumeration failed")
    return frozenset(int(line.strip()) for line in result.stdout.splitlines() if line.strip())


def _window_pid(hwnd: int) -> int:
    return int(win32process.GetWindowThreadProcessId(int(hwnd))[1])


def _open_process(pid: int) -> Any:
    return win32api.OpenProcess(0x0001 | 0x1000 | 0x00100000, False, pid)


def _identity(handle: Any) -> tuple[int, Path, datetime]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    query = kernel.QueryFullProcessImageNameW
    query.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    query.restype = wintypes.BOOL
    size = wintypes.DWORD(32768)
    buffer = ctypes.create_unicode_buffer(size.value)
    if not query(int(handle), 0, buffer, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    created = win32process.GetProcessTimes(handle)["CreationTime"]
    return int(win32process.GetProcessId(handle)), Path(buffer.value).resolve(strict=True), created


def _running(handle: Any) -> bool:
    result = win32event.WaitForSingleObject(handle, 0)
    if result not in (0, 258):
        raise AppError("E201", "could not verify CAD process liveness")
    return result == 258


def _terminate(handle: Any) -> None:
    win32process.TerminateProcess(handle, 1)


def _close_handle(handle: Any) -> None:
    win32api.CloseHandle(handle)


@dataclass
class OwnedProcess(AbstractContextManager["OwnedProcess"]):
    pid: int
    creation_time: datetime
    executable: Path
    handle: Any

    def __enter__(self) -> "OwnedProcess":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        handle, self.handle = self.handle, None
        if handle is not None:
            _close_handle(handle)

    def terminate_if_running(self) -> None:
        if self.handle is not None and _running(self.handle):
            _terminate(self.handle)


def capture_owned_process(
    candidate: CadCandidate, hwnd: int, before: frozenset[int], after: frozenset[int],
    *, started_at: datetime | None = None,
) -> OwnedProcess:
    handle = None
    try:
        pid = _window_pid(hwnd)
        products = _product_pids(candidate)
        if pid <= 0 or pid in before or pid not in after or products - before != {pid}:
            raise AppError("E201", "could not prove ownership of exactly one new CAD process")
        handle = _open_process(pid)
        if handle is None:
            raise AppError("E201", "could not capture owned CAD handle")
        identity = _identity(handle)
        expected = candidate.executable.resolve(strict=True)
        if identity[0] != pid or identity[1] != expected or not _running(handle):
            raise AppError("E201", "CAD process identity differs from selected installation")
        if started_at is not None and not started_at <= identity[2] <= datetime.now(timezone.utc):
            raise AppError("E201", "CAD process creation time does not prove ownership")
        if _window_pid(hwnd) != pid or _identity(handle) != identity or not _running(handle):
            raise AppError("E201", "CAD process identity changed during ownership proof")
        return OwnedProcess(pid, identity[2], identity[1], handle)
    except Exception as exc:
        if handle is not None:
            _close_handle(handle)
        if isinstance(exc, AppError):
            raise
        raise AppError("E201", "could not prove CAD process ownership; no CAD changes made") from exc
