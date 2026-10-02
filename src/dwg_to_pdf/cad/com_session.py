from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from datetime import datetime, timezone
import gc
from pathlib import Path
import subprocess
from typing import Any, Iterator, Callable

import pythoncom
import win32api
import win32com.client
import win32event
import win32process
import winerror

from ..errors import AppError
from .contracts import CadDocument
from .selection import CadCandidate
from .process_ownership import OwnedProcess, _all_pids, capture_owned_process
from .diagnostics import emit

_MUTEX_NAME = "Local\\DWG_TO_PDF_CAD_COM"
_LEGACY_MUTEX_NAME = "Local\\DWG_TO_PDF_GSTARCAD_COM"
_PROCESS_TERMINATE = 0x0001
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_PROCESS_HANDLE_ACCESS = (
    _PROCESS_TERMINATE | _PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE
)
_WAIT_OBJECT_0 = 0
_PROCESS_EXIT_TIMEOUT_MS = 30_000


def _open_owned_process_handle(pid: int) -> Any:
    """Capture an exact process object while ownership proof is still fresh.

    A Windows process handle identifies the process object, unlike a PID which
    may be reused after the original process exits.  It is deliberately opened
    with only the rights needed to wait, query, and terminate the owned server.
    """

    try:
        handle = win32api.OpenProcess(_PROCESS_HANDLE_ACCESS, False, pid)
    except Exception as exc:
        raise AppError("E201", "could not capture the owned CAD process handle") from exc
    if handle is None:
        raise AppError("E201", "could not capture the owned CAD process handle")
    return handle


def _wait_for_process_exit(handle: Any) -> bool:
    """Return whether this exact process object exited after COM Quit."""

    try:
        return win32event.WaitForSingleObject(handle, _PROCESS_EXIT_TIMEOUT_MS) == _WAIT_OBJECT_0
    except Exception:
        return False


def _terminate_owned_process_handle(handle: Any) -> None:
    """Force-stop only the exact object captured during ownership proof."""

    try:
        win32process.TerminateProcess(handle, 1)
    except Exception:
        # Shutdown is best-effort; COM/mutex cleanup must still complete.
        pass


def _close_process_handle(handle: Any) -> None:
    try:
        win32api.CloseHandle(handle)
    except Exception:
        pass


def _create_owned_mutex(name: str) -> Any:
    handle = win32event.CreateMutex(None, True, name)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        win32api.CloseHandle(handle)
        raise AppError("E201", "another DWG to PDF COM session is active")
    if handle is None:
        raise AppError("E201", "could not acquire CAD COM mutex")
    return handle


def _close_mutex(handle: Any) -> None:
    try:
        win32event.ReleaseMutex(handle)
    except Exception:
        pass
    win32api.CloseHandle(handle)


def _window_pid(hwnd: int) -> int:
    try:
        _, pid = win32process.GetWindowThreadProcessId(int(hwnd))
        return int(pid)
    except Exception as exc:
        raise AppError("E201", "could not identify CAD COM window process") from exc


def _gstar_pids() -> set[int]:
    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Get-Process -Name gcad -ErrorAction SilentlyContinue | ForEach-Object { $_.Id }",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise AppError("E201", "could not enumerate CAD processes") from exc
    if result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip():
        return set()
    if result.returncode != 0:
        raise AppError("E201", "CAD process enumeration failed")
    values: set[int] = set()
    for line in result.stdout.splitlines():
        raw = line.strip()
        if not raw:
            continue
        if not raw.isdigit():
            raise AppError("E201", "CAD process enumeration returned invalid data")
        values.add(int(raw))
    return values


class ComSession(AbstractContextManager["ComSession"]):
    """A reusable one-document-at-a-time session for a proven-owned process."""

    def __init__(self, candidate: CadCandidate | None, document_factory: Callable[[Any], CadDocument]) -> None:
        self.candidate = candidate
        self._document_factory = document_factory
        self.app: Any | None = None
        self.document: Any | None = None
        self._wrapped_document: CadDocument | None = None
        self.owned_pid: int | None = None
        self._owned_process_handle: Any | None = None
        self._owned_process: OwnedProcess | None = None
        self.reported_version: str | None = None
        self.mutex: Any | None = None
        self._legacy_mutex: Any | None = None
        self._com_initialized = False
        self._owns_app = False
        self._document_close_failed = False

    @property
    def is_usable(self) -> bool:
        return self.app is not None and self._owns_app and not self._document_close_failed

    def _resolve_candidate(self) -> CadCandidate:
        if self.candidate is None:
            raise AppError("E202", "CAD candidate is required")
        return self.candidate

    def __enter__(self) -> "ComSession":
        if self.mutex is not None or self._com_initialized or self.app is not None:
            raise RuntimeError("session cannot be entered more than once")
        try:
            emit("start")
            pythoncom.CoInitialize()
            self._com_initialized = True
            self.mutex = _create_owned_mutex(_MUTEX_NAME)
            self._legacy_mutex = _create_owned_mutex(_LEGACY_MUTEX_NAME)
            self.candidate = self._resolve_candidate()
            before = _all_pids()
            started_at = datetime.now(timezone.utc)
            self.app = win32com.client.DispatchEx(self.candidate.prog_id)
            process = capture_owned_process(self.candidate, self.app.HWND, before, _all_pids(), started_at=started_at)
            self._owned_process = process
            self._owned_process_handle = process.handle
            self.owned_pid = process.pid
            self._owns_app = True
            self.app.Visible = False
            try:
                version = self.app.Version
                self.reported_version = version if isinstance(version, str) and version.strip() else None
            except Exception:
                self.reported_version = None
            emit("ready", reported_version=self.reported_version)
            return self
        except BaseException as error:
            emit("start", getattr(error, "code", "E201"))
            self._release()
            raise

    def open_readonly_copy(self, path: Path) -> CadDocument:
        if not self.is_usable:
            raise AppError("E201", "CAD batch session is not usable")
        if self.document is not None:
            raise AppError(
                "E201",
                "one CAD process may open only one file; close it before opening another",
            )
        source = Path(path).resolve(strict=True)
        if not source.is_file() or source.suffix.casefold() != ".dwg":
            raise AppError("E203", "source must be an existing DWG file", source)
        try:
            raw = self.app.Documents.Open(str(source), True)
        except Exception as exc:
            raise AppError("E203", "CAD could not open source read-only", source) from exc
        # Track every successfully opened raw document before any COM property
        # access can fail, so all later errors cross the same close boundary.
        self.document = raw
        try:
            readonly = bool(getattr(raw, "ReadOnly", False))
        except Exception as exc:
            try:
                self.close_document()
            except AppError as close_exc:
                raise AppError(
                    "E203",
                    "CAD could not verify source read-only and could not close it",
                    source,
                ) from close_exc
            raise AppError("E203", "CAD could not verify source read-only", source) from exc
        if not readonly:
            try:
                self.close_document()
            except AppError as exc:
                raise AppError(
                    "E203",
                    "CAD did not open source read-only and could not close it",
                    source,
                ) from exc
            raise AppError("E203", "CAD did not open source read-only", source)
        self._wrapped_document = self._document_factory(raw)
        return self._wrapped_document

    def _open_working_copy(self, workspace: Any) -> CadDocument:
        """Open one authorized workspace copy; callers use working_document()."""

        from ..temp_workspace import SourceWorkspace

        if not self.is_usable:
            raise AppError("E201", "CAD batch session is not usable")
        if self.document is not None:
            raise AppError(
                "E201",
                "one CAD process may open only one file; close it before opening another",
            )
        if not isinstance(workspace, SourceWorkspace):
            raise AppError("E400", "active source workspace is required")
        try:
            working_copy = workspace.authorized_copy()
        except AppError:
            raise
        except Exception as exc:
            raise AppError("E400", "active source workspace is required") from exc
        try:
            raw = self.app.Documents.Open(str(working_copy), False)
        except Exception as exc:
            raise AppError("E203", "CAD could not open the temporary DWG copy", working_copy) from exc
        self.document = raw
        try:
            readonly = bool(raw.ReadOnly)
            if Path(raw.FullName).resolve(strict=True) != working_copy.resolve(strict=True):
                raise AppError("E203", "CAD opened a different document than the authorized copy")
        except Exception as exc:
            try:
                self.close_document()
            except AppError as close_exc:
                raise AppError(
                    "E203",
                    "CAD could not verify or close the temporary DWG copy",
                    working_copy,
                ) from close_exc
            raise AppError("E203", "CAD could not verify the temporary DWG copy", working_copy) from exc
        if readonly:
            try:
                self.close_document()
            except AppError as close_exc:
                raise AppError(
                    "E203",
                    "temporary DWG copy was read-only and could not be closed",
                    working_copy,
                ) from close_exc
            raise AppError("E203", "temporary DWG copy was opened read-only", working_copy)
        self._wrapped_document = self._document_factory(raw)
        self._wrapped_document.configure_extraction(True)
        return self._wrapped_document

    @contextmanager
    def working_document(self, workspace: Any) -> Iterator[CadDocument]:
        """Own the writable document boundary and always close without saving."""

        document = self._open_working_copy(workspace)
        primary_error: BaseException | None = None
        try:
            yield document
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            try:
                self.close_document()
            except AppError as close_error:
                if primary_error is not None:
                    close_error.add_note(
                        f"Primary failure: {type(primary_error).__name__}: {primary_error}"
                    )
                    raise close_error from primary_error
                raise

    def close_document(self) -> None:
        raw = self.document
        wrapped = self._wrapped_document
        self.document = None
        self._wrapped_document = None
        if wrapped is not None:
            wrapped.raw = None
        if raw is None:
            return
        try:
            raw.Close(False)
        except Exception as exc:
            self._document_close_failed = True
            raise AppError("E203", "CAD could not close the current document") from exc
        finally:
            # Release document and SelectionSet proxies before another file is
            # opened in this same automation server.
            gc.collect()

    def __exit__(self, exc_type, exc, tb) -> None:
        self._release()

    def _release(self) -> None:
        if self._owns_app:
            emit("close", reported_version=self.reported_version)
        process_handle, self._owned_process_handle = self._owned_process_handle, None
        process, self._owned_process = self._owned_process, None
        try:
            self.close_document()
        except AppError:
            # Shutdown must continue after a broken document boundary. The
            # failure already made this session unusable for further opens.
            pass
        if self.app is not None:
            if self._owns_app:
                try:
                    self.app.Quit()
                except Exception:
                    pass
            self.app = None
        self._owns_app = False
        gc.collect()

        try:
            if process_handle is not None and not _wait_for_process_exit(process_handle):
                if process is not None:
                    process.terminate_if_running()
                else:
                    _terminate_owned_process_handle(process_handle)
        except Exception:
            # A wait/termination API failure must not strand COM or the mutex.
            pass
        finally:
            if process_handle is not None:
                try:
                    if process is not None:
                        process.close()
                    else:
                        _close_process_handle(process_handle)
                except Exception:
                    pass
            self.owned_pid = None
            if self._com_initialized:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
                finally:
                    self._com_initialized = False
            for attribute in ("_legacy_mutex", "mutex"):
                mutex = getattr(self, attribute)
                setattr(self, attribute, None)
                if mutex is None:
                    continue
                try:
                    _close_mutex(mutex)
                except Exception:
                    pass
