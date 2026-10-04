from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import sys
from types import SimpleNamespace

import pytest

from dwg_to_pdf.errors import AppError
from dwg_to_pdf.gstarcad.com_session import GstarSession, _gstar_pids
from dwg_to_pdf.gstarcad.discovery import require_registered_prog_id
from dwg_to_pdf.gstarcad.media_resolver import require_plot_environment
from dwg_to_pdf.temp_workspace import SourceWorkspace
from dwg_to_pdf.cad.selection import CadCandidate


@pytest.fixture(autouse=True)
def ownership_boundary(monkeypatch):
    executable = Path(sys.executable).resolve()
    candidate = CadCandidate("gstarcad", "GStarCAD.Application.26", "fake", executable, "GstarCAD", None)
    monkeypatch.setattr(GstarSession, "_resolve_candidate", lambda self: candidate)
    monkeypatch.setattr("dwg_to_pdf.cad.process_ownership._product_pids", lambda _: frozenset({7}))
    # Stable creation timestamp is captured on first identity read, after dispatch.
    times = []
    def identity(handle):
        if not times:
            times.append(datetime.now(timezone.utc))
        return 7, executable, times[0]
    monkeypatch.setattr("dwg_to_pdf.cad.process_ownership._identity", identity)
    monkeypatch.setattr("dwg_to_pdf.cad.process_ownership._running", lambda _: True)


def test_discovery_rejects_missing_registration(monkeypatch) -> None:
    def missing(*args):
        raise FileNotFoundError

    monkeypatch.setattr("dwg_to_pdf.gstarcad.discovery.winreg.OpenKey", missing)
    with pytest.raises(AppError, match="not registered") as raised:
        require_registered_prog_id("GStarCAD.Application.26")
    assert raised.value.code == "E202"


def test_gstar_pid_enumeration_treats_empty_process_set_as_valid(monkeypatch) -> None:
    monkeypatch.setattr(
        "dwg_to_pdf.cad.com_session.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )
    assert _gstar_pids() == set()


def test_gstar_pid_enumeration_preserves_real_powershell_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "dwg_to_pdf.cad.com_session.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="access denied"),
    )
    with pytest.raises(AppError) as raised:
        _gstar_pids()
    assert raised.value.code == "E201"


class FakeLayout:
    def __init__(self):
        self.ConfigName = ""
        self.CanonicalMediaName = ""

    def GetPlotDeviceNames(self):
        return ["DWG To PDF.pc3"]

    def RefreshPlotDeviceInfo(self):
        pass

    def GetPlotStyleTableNames(self):
        return ["monochrome.ctb"]

    def GetCanonicalMediaNames(self):
        return ["ISO_A4", "LETTER"]

    def GetPaperSize(self):
        return (297.0, 210.0) if self.CanonicalMediaName == "ISO_A4" else (279.4, 215.9)


def test_plot_environment_resolves_a4_by_measured_size() -> None:
    layout = FakeLayout()
    assert require_plot_environment(layout, ()) == "ISO_A4"
    assert layout.ConfigName == "DWG To PDF.pc3"


def test_session_partial_enter_failure_cleans_up_without_unbalanced_com(monkeypatch) -> None:
    events = []
    monkeypatch.setattr("dwg_to_pdf.cad.com_session._create_owned_mutex", lambda name: "mutex")
    monkeypatch.setattr("dwg_to_pdf.cad.com_session.pythoncom.CoInitialize", lambda: events.append("init"))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session.pythoncom.CoUninitialize", lambda: events.append("uninit"))
    monkeypatch.setattr(GstarSession, "_resolve_candidate", lambda self: (_ for _ in ()).throw(AppError("E202", "bad")))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session._close_mutex", lambda mutex: events.append("mutex-close"))

    session = GstarSession("bad")
    with pytest.raises(AppError, match="bad"):
        session.__enter__()
    session._release()
    assert events == ["init", "uninit", "mutex-close", "mutex-close"]


def test_session_fails_closed_when_window_pid_does_not_prove_new_process(monkeypatch) -> None:
    events = []
    app = SimpleNamespace(HWND=123, Visible=True, Quit=lambda: events.append("quit"))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session._create_owned_mutex", lambda name: "mutex")
    monkeypatch.setattr("dwg_to_pdf.cad.com_session._close_mutex", lambda mutex: events.append("mutex-close"))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session.pythoncom.CoInitialize", lambda: events.append("init"))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session.pythoncom.CoUninitialize", lambda: events.append("uninit"))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session._all_pids", lambda: {7})
    monkeypatch.setattr("dwg_to_pdf.cad.com_session.win32com.client.DispatchEx", lambda prog_id: app)
    monkeypatch.setattr("dwg_to_pdf.cad.process_ownership._window_pid", lambda hwnd: 7)

    with pytest.raises(AppError, match="ownership") as raised:
        GstarSession("GStarCAD.Application.26").__enter__()
    assert raised.value.code == "E201"
    # An application whose PID was already present may be user-owned. Releasing
    # our COM reference is safe; calling Quit would not be.
    assert app.Visible is True
    assert events == ["init", "uninit", "mutex-close", "mutex-close"]


def test_session_requires_exact_process_handle_after_ownership_proof(monkeypatch) -> None:
    events: list[object] = []
    app = SimpleNamespace(HWND=123, Visible=True, Quit=lambda: events.append("quit"))
    handle = object()
    pids = iter((set(), {7}))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session._create_owned_mutex", lambda name: "mutex")
    monkeypatch.setattr("dwg_to_pdf.cad.com_session._close_mutex", lambda mutex: events.append("mutex-close"))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session.pythoncom.CoInitialize", lambda: events.append("init"))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session.pythoncom.CoUninitialize", lambda: events.append("uninit"))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session._all_pids", lambda: next(pids))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session.win32com.client.DispatchEx", lambda prog_id: app)
    monkeypatch.setattr("dwg_to_pdf.cad.process_ownership._window_pid", lambda hwnd: 7)
    monkeypatch.setattr("dwg_to_pdf.cad.process_ownership._open_process", lambda pid: handle)
    monkeypatch.setattr("dwg_to_pdf.cad.com_session._wait_for_process_exit", lambda captured: True)
    monkeypatch.setattr("dwg_to_pdf.cad.process_ownership._close_handle", lambda captured: events.append(("handle-close", captured)))

    session = GstarSession("GStarCAD.Application.26").__enter__()
    assert session.owned_pid == 7
    assert session._owned_process_handle is handle
    session._release()

    assert events == ["init", "quit", ("handle-close", handle), "uninit", "mutex-close", "mutex-close"]


def test_handle_capture_failure_never_sets_owns_app_or_mutates_cad(monkeypatch) -> None:
    events: list[object] = []
    app = SimpleNamespace(HWND=123, Visible=True, Quit=lambda: events.append("quit"))
    pids = iter((set(), {7}))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session._create_owned_mutex", lambda name: "mutex")
    monkeypatch.setattr("dwg_to_pdf.cad.com_session._close_mutex", lambda mutex: events.append("mutex-close"))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session.pythoncom.CoInitialize", lambda: events.append("init"))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session.pythoncom.CoUninitialize", lambda: events.append("uninit"))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session._all_pids", lambda: next(pids))
    monkeypatch.setattr("dwg_to_pdf.cad.com_session.win32com.client.DispatchEx", lambda prog_id: app)
    monkeypatch.setattr("dwg_to_pdf.cad.process_ownership._window_pid", lambda hwnd: 7)
    monkeypatch.setattr(
        "dwg_to_pdf.cad.process_ownership._open_process",
        lambda pid: (_ for _ in ()).throw(AppError("E201", "no handle")),
    )
    monkeypatch.setattr(
        "dwg_to_pdf.cad.com_session._terminate_owned_process_handle",
        lambda captured: pytest.fail("session without a captured handle must not force terminate"),
    )

    with pytest.raises(AppError, match="no handle") as raised:
        GstarSession("GStarCAD.Application.26").__enter__()

    assert raised.value.code == "E201"
    assert app.Visible is True
    assert events == ["init", "uninit", "mutex-close", "mutex-close"]


def test_session_opens_at_most_one_existing_file_readonly(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"dwg")
    opened = []
    raw_document = SimpleNamespace(ReadOnly=True)
    documents = SimpleNamespace(Open=lambda path, readonly: opened.append((path, readonly)) or raw_document)
    session = GstarSession("unused")
    session.app = SimpleNamespace(Documents=documents)
    session._owns_app = True

    document = session.open_readonly_copy(source)
    assert document.raw is raw_document
    assert opened == [(str(source.resolve()), True)]
    with pytest.raises(AppError, match="one file"):
        session.open_readonly_copy(source)


def test_session_release_invalidates_returned_document_before_quit(tmp_path: Path) -> None:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"dwg")
    events = []
    raw_document = SimpleNamespace(
        ReadOnly=True,
        Close=lambda save: events.append(("close", save)),
    )
    session = GstarSession("unused")
    session.app = SimpleNamespace(
        Documents=SimpleNamespace(Open=lambda path, readonly: raw_document),
        Quit=lambda: events.append(("quit",)),
    )
    session._owns_app = True

    wrapped = session.open_readonly_copy(source)
    session._release()

    assert wrapped.raw is None
    assert events == [("close", False), ("quit",)]


class FakeRawDocument:
    def __init__(
        self,
        *,
        readonly: bool = True,
        readonly_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self._readonly = readonly
        self.readonly_error = readonly_error
        self.close_error = close_error
        self.close_arguments: list[bool] = []

    @property
    def ReadOnly(self) -> bool:
        if self.readonly_error is not None:
            raise self.readonly_error
        return self._readonly

    def Close(self, save: bool) -> None:
        self.close_arguments.append(save)
        if self.close_error is not None:
            raise self.close_error


class FakeDocuments:
    def __init__(self, documents: list[FakeRawDocument]) -> None:
        self._documents = iter(documents)
        self.opened: list[tuple[str, bool]] = []

    def Open(self, path: str, readonly: bool) -> FakeRawDocument:
        self.opened.append((path, readonly))
        document = next(self._documents)
        document.FullName = path
        return document


def _open_fake_session(documents: list[FakeRawDocument]) -> GstarSession:
    session = GstarSession("unused")
    session.app = SimpleNamespace(Documents=FakeDocuments(documents), Quit=lambda: None)
    session._owns_app = True
    session.owned_pid = 4242
    return session


def test_session_reuses_owned_app_after_each_document_is_closed(tmp_path: Path) -> None:
    first = tmp_path / "first.dwg"
    second = tmp_path / "second.dwg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    first_raw = FakeRawDocument()
    second_raw = FakeRawDocument()
    session = _open_fake_session([first_raw, second_raw])

    first_wrapped = session.open_readonly_copy(first)
    session.close_document()
    second_wrapped = session.open_readonly_copy(second)
    session.close_document()

    assert session.app.Documents.opened == [
        (str(first.resolve()), True),
        (str(second.resolve()), True),
    ]
    assert first_raw.close_arguments == [False]
    assert second_raw.close_arguments == [False]
    assert first_wrapped.raw is None
    assert second_wrapped.raw is None
    assert session.owned_pid == 4242
    assert session.is_usable is True


def test_session_rejects_second_open_until_current_document_is_closed(tmp_path: Path) -> None:
    first = tmp_path / "first.dwg"
    second = tmp_path / "second.dwg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    session = _open_fake_session([FakeRawDocument(), FakeRawDocument()])

    session.open_readonly_copy(first)

    with pytest.raises(AppError) as raised:
        session.open_readonly_copy(second)
    assert raised.value.code == "E201"
    assert session.app.Documents.opened == [(str(first.resolve()), True)]


def test_close_document_is_idempotent_and_never_saves(tmp_path: Path) -> None:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"source")
    raw = FakeRawDocument()
    session = _open_fake_session([raw])
    wrapped = session.open_readonly_copy(source)

    session.close_document()
    session.close_document()

    assert raw.close_arguments == [False]
    assert wrapped.raw is None
    assert session.document is None


def test_close_failure_marks_session_unusable_and_never_saves(tmp_path: Path) -> None:
    source = tmp_path / "bad-close.dwg"
    source.write_bytes(b"source")
    raw = FakeRawDocument(close_error=RuntimeError("close failed"))
    session = _open_fake_session([raw])
    wrapped = session.open_readonly_copy(source)

    with pytest.raises(AppError) as raised:
        session.close_document()

    assert raised.value.code == "E203"
    assert session.is_usable is False
    assert raw.close_arguments == [False]
    assert wrapped.raw is None
    assert session.document is None
    with pytest.raises(AppError) as later_open:
        session.open_readonly_copy(source)
    assert later_open.value.code == "E201"


def test_working_document_preserves_body_error_when_close_also_fails(tmp_path: Path) -> None:
    source = tmp_path / "body-and-close-fail.dwg"
    source.write_bytes(b"source")
    raw = FakeRawDocument(readonly=False, close_error=RuntimeError("close failed"))
    session = _open_fake_session([raw])

    with SourceWorkspace(source) as workspace:
        with pytest.raises(AppError) as raised:
            with session.working_document(workspace):
                raise AppError("E303", "non-uniform block scale")

    assert raised.value.code == "E203"
    assert any("Primary failure" in note for note in getattr(raised.value, "__notes__", ()))
    assert isinstance(raised.value.__cause__, AppError)
    assert raised.value.__cause__.code == "E303"


def test_shutdown_after_close_failure_is_safe_and_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "bad-close.dwg"
    source.write_bytes(b"source")
    events: list[str] = []
    raw = FakeRawDocument(close_error=RuntimeError("close failed"))
    session = _open_fake_session([raw])
    session.app.Quit = lambda: events.append("quit")
    session.open_readonly_copy(source)

    with pytest.raises(AppError, match="close"):
        session.close_document()
    session._release()
    session._release()

    assert raw.close_arguments == [False]
    assert events == ["quit"]
    assert session.owned_pid is None


def test_non_readonly_open_with_failed_close_breaks_session_and_never_opens_again(
    tmp_path: Path,
) -> None:
    source = tmp_path / "not-readonly.dwg"
    source.write_bytes(b"source")
    raw = FakeRawDocument(readonly=False, close_error=RuntimeError("close failed"))
    session = _open_fake_session([raw, FakeRawDocument()])
    events: list[str] = []
    session.app.Quit = lambda: events.append("owned-quit")

    with pytest.raises(AppError) as raised:
        session.open_readonly_copy(source)

    assert raised.value.code == "E203"
    assert raw.close_arguments == [False]
    assert session.is_usable is False
    assert session._document_close_failed is True
    assert session.document is None
    with pytest.raises(AppError) as later_open:
        session.open_readonly_copy(source)
    assert later_open.value.code == "E201"
    assert len(session.app.Documents.opened) == 1

    session._release()
    session._release()

    assert events == ["owned-quit"]
    assert session.owned_pid is None


def test_unreadable_readonly_property_with_failed_close_breaks_session(
    tmp_path: Path,
) -> None:
    source = tmp_path / "unreadable-readonly.dwg"
    source.write_bytes(b"source")
    raw = FakeRawDocument(
        readonly_error=RuntimeError("ReadOnly property failed"),
        close_error=RuntimeError("close failed"),
    )
    session = _open_fake_session([raw, FakeRawDocument()])
    events: list[str] = []
    session.app.Quit = lambda: events.append("owned-quit")

    with pytest.raises(AppError) as raised:
        session.open_readonly_copy(source)

    assert raised.value.code == "E203"
    assert raw.close_arguments == [False]
    assert session.is_usable is False
    assert session._document_close_failed is True
    assert session.document is None
    with pytest.raises(AppError) as later_open:
        session.open_readonly_copy(source)
    assert later_open.value.code == "E201"
    assert len(session.app.Documents.opened) == 1

    session._release()
    session._release()

    assert events == ["owned-quit"]
    assert session.owned_pid is None


def test_handle_wait_and_close_failures_cannot_block_com_or_mutex_cleanup(
    monkeypatch,
) -> None:
    events: list[object] = []
    session = GstarSession("unused")
    session.app = SimpleNamespace(Quit=lambda: events.append("quit"))
    session._owns_app = True
    session.owned_pid = 4242
    session._owned_process_handle = object()
    session._com_initialized = True
    session.mutex = "mutex"
    monkeypatch.setattr(
        "dwg_to_pdf.cad.com_session._wait_for_process_exit",
        lambda handle: (_ for _ in ()).throw(OSError("wait failure")),
    )
    monkeypatch.setattr(
        "dwg_to_pdf.cad.com_session._terminate_owned_process_handle",
        lambda handle: (_ for _ in ()).throw(RuntimeError("terminate failure")),
    )
    monkeypatch.setattr(
        "dwg_to_pdf.cad.com_session._close_process_handle",
        lambda handle: (_ for _ in ()).throw(RuntimeError("close failure")),
    )
    monkeypatch.setattr(
        "dwg_to_pdf.cad.com_session.pythoncom.CoUninitialize",
        lambda: events.append("uninit"),
    )
    monkeypatch.setattr(
        "dwg_to_pdf.cad.com_session._close_mutex",
        lambda mutex: events.append(("mutex-close", mutex)),
    )

    session._release()
    session._release()

    assert events == ["quit", "uninit", ("mutex-close", "mutex")]
    assert session.owned_pid is None
    assert session._com_initialized is False
    assert session.mutex is None
