from pathlib import Path
from types import SimpleNamespace

import pytest

from dwg_to_pdf.cad import com_session
from dwg_to_pdf.cad.selection import CadCandidate
from dwg_to_pdf.errors import AppError
from dwg_to_pdf.temp_workspace import SourceWorkspace


class App:
    HWND = 123
    Version = "25.0-test"

    def __init__(self):
        self.writes = []
        self.quit_count = 0
        self.opened = []
        self.closed = []
        self.Documents = SimpleNamespace(Open=self.open)

    @property
    def Visible(self):
        return True

    @Visible.setter
    def Visible(self, value):
        self.writes.append(("Visible", value))

    def Quit(self):
        self.quit_count += 1

    def open(self, path, readonly):
        self.opened.append((path, readonly))
        return SimpleNamespace(ReadOnly=readonly, FullName=path, Close=lambda save: self.closed.append(save))


@pytest.fixture
def setup_session(monkeypatch, tmp_path):
    app = App()
    events = []
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "clsid", tmp_path / "acad.exe", "AutoCAD", None)
    monkeypatch.setattr(com_session.pythoncom, "CoInitialize", lambda: events.append("init"))
    monkeypatch.setattr(com_session.pythoncom, "CoUninitialize", lambda: events.append("uninit"))
    monkeypatch.setattr(com_session, "_create_owned_mutex", lambda name: name)
    monkeypatch.setattr(com_session, "_close_mutex", lambda name: events.append(("mutex-close", name)))
    monkeypatch.setattr(com_session, "_all_pids", lambda: frozenset({1}))
    monkeypatch.setattr(com_session.win32com.client, "DispatchEx", lambda _: app)
    process = SimpleNamespace(pid=71, handle=object(), close=lambda: events.append("handle-close"), terminate_if_running=lambda: events.append("terminate"))
    monkeypatch.setattr(com_session, "capture_owned_process", lambda *args, **kwargs: process)
    monkeypatch.setattr(com_session, "_wait_for_process_exit", lambda handle: True)
    session = com_session.ComSession(candidate, lambda raw: SimpleNamespace(raw=raw, configure_extraction=lambda enabled: None))
    return session, app, events


def test_reused_user_session_has_no_writes_or_quit(setup_session, monkeypatch):
    session, app, events = setup_session
    monkeypatch.setattr(com_session, "capture_owned_process", lambda *args, **kwargs: (_ for _ in ()).throw(AppError("E201", "ownership")))
    with pytest.raises(AppError):
        session.__enter__()
    assert app.writes == []
    assert app.opened == []
    assert app.quit_count == 0
    assert "terminate" not in events
    assert "uninit" in events


def test_partial_initialization_releases_only_owned_resources(setup_session, monkeypatch):
    session, app, events = setup_session
    monkeypatch.setattr(com_session, "_create_owned_mutex", lambda _: (_ for _ in ()).throw(AppError("E201", "busy")))
    with pytest.raises(AppError):
        session.__enter__()
    assert events == ["init", "uninit"]
    assert not app.writes and app.quit_count == 0


def test_second_file_reuses_session(setup_session, tmp_path):
    session, app, events = setup_session
    source = tmp_path / "source.dwg"
    source.write_bytes(b"AC1032original")
    with session:
        assert session.reported_version == "25.0-test"
        for _ in range(2):
            with SourceWorkspace(source) as workspace:
                with session.working_document(workspace) as document:
                    assert document.raw.FullName != str(source)
    assert app.writes == [("Visible", False)]
    assert app.closed == [False, False]
    assert app.quit_count == 1
    assert len(app.opened) == 2
    assert source.read_bytes() == b"AC1032original"
    assert "handle-close" in events


def test_wrong_document_identity_rejected(setup_session, tmp_path):
    session, app, _ = setup_session
    source = tmp_path / "source.dwg"
    source.write_bytes(b"AC1032original")
    app.Documents.Open = lambda *args: SimpleNamespace(ReadOnly=False, FullName=str(source), Close=lambda save: app.closed.append(save))
    with session, SourceWorkspace(source) as workspace:
        with pytest.raises(AppError) as error:
            with session.working_document(workspace):
                pytest.fail("must not expose wrong drawing")
        assert error.value.code == "E203"
    assert app.closed == [False]


@pytest.mark.parametrize("stage", ["start", "ready", "close"])
@pytest.mark.parametrize("sink_error", [OSError, BrokenPipeError, ValueError])
def test_diagnostic_sink_failure_cannot_strand_session(setup_session, monkeypatch, stage, sink_error):
    import sys
    from dwg_to_pdf.cad.diagnostics import diagnostic_scope
    session, app, events = setup_session
    class Sink:
        def write(self, value):
            if f'"stage": "{stage}"' in value:
                raise sink_error("closed diagnostic destination")
        def flush(self): pass
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stderr", Sink())
        with diagnostic_scope(session.candidate, "test"), session:
            assert session.is_usable
    assert app.quit_count == 1
    assert "handle-close" in events and "uninit" in events
    assert session.mutex is None and session._legacy_mutex is None
    assert not session._owns_app


def test_owned_autocad_waits_through_busy_startup_before_mutation(setup_session, monkeypatch):
    import pywintypes
    from dwg_to_pdf.autocad.com_session import AutoCADSession
    _, app, events = setup_session
    ready = {"value": False}
    states = iter(("rejected", False, True))
    def state():
        value = next(states)
        if value == "rejected":
            raise pywintypes.com_error(-2147418111, "busy", None, None)
        ready["value"] = value
        return SimpleNamespace(IsQuiescent=value)
    app.GetAcadState = state
    app.Documents.Count = 1
    original_setter = App.Visible.fset
    def visible(instance, value):
        if not ready["value"]:
            raise ValueError("mutation before AutoCAD readiness")
        original_setter(instance, value)
    monkeypatch.setattr(App, "Visible", property(App.Visible.fget, visible))
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "clsid", Path("acad.exe"), "AutoCAD", None)
    with AutoCADSession(candidate) as session:
        assert session.is_usable
    assert app.quit_count == 1 and "handle-close" in events


def test_owned_autocad_readiness_timeout_releases_resources(setup_session, monkeypatch):
    import time
    from dwg_to_pdf.autocad import com_session as autocad
    _, app, events = setup_session
    app.GetAcadState = lambda: SimpleNamespace(IsQuiescent=False)
    ticks = iter((0., 121.))
    monkeypatch.setattr(time, "monotonic", lambda: next(ticks))
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "clsid", Path("acad.exe"), "AutoCAD", None)
    session = autocad.AutoCADSession(candidate)
    with pytest.raises(AppError) as error:
        session.__enter__()
    assert error.value.code == "E201"
    assert app.writes == [] and app.quit_count == 1
    assert "handle-close" in events and "uninit" in events


def test_owned_autocad_permanent_readiness_failure_is_not_retried(setup_session):
    import pywintypes
    from dwg_to_pdf.autocad.com_session import AutoCADSession
    _, app, events = setup_session
    def state():
        raise pywintypes.com_error(-2147024891, "access denied", None, None)
    app.GetAcadState = state
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "clsid", Path("acad.exe"), "AutoCAD", None)
    with pytest.raises(AppError) as error:
        AutoCADSession(candidate).__enter__()
    assert error.value.code == "E201"
    assert app.writes == [] and app.quit_count == 1


@pytest.mark.parametrize("phase", ["open", "close"])
def test_autocad_waits_at_document_boundary_without_repeating_mutations(setup_session, tmp_path, phase):
    import pywintypes
    from dwg_to_pdf.autocad.com_session import AutoCADSession
    _, app, _ = setup_session
    pending = [0]
    def state():
        pending[0] = max(0, pending[0] - 1)
        return SimpleNamespace(IsQuiescent=pending[0] == 0)
    app.GetAcadState = state
    app.Documents.Count = 1
    class Document:
        def __init__(self, path): self.FullName = path
        @property
        def ReadOnly(self):
            if pending[0]: raise pywintypes.com_error(-2147418111, "opening", None, None)
            return False
        def Close(self, save):
            if pending[0]: raise pywintypes.com_error(-2147418111, "busy before close", None, None)
            app.closed.append(save)
    def open_document(path, readonly):
        app.opened.append((path, readonly))
        if phase == "open": pending[0] = 2
        return Document(path)
    app.Documents.Open = open_document
    source = tmp_path / "source.dwg"
    source.write_bytes(b"AC1032original")
    with AutoCADSession(CadCandidate("autocad", "AutoCAD.Application.25", "clsid", Path("acad.exe"), "AutoCAD", None)) as session:
        with SourceWorkspace(source) as workspace:
            with session.working_document(workspace):
                if phase == "close": pending[0] = 2
    assert len(app.opened) == 1
    assert app.closed == [False]
    assert app.quit_count == 1
    assert source.read_bytes() == b"AC1032original"


def test_open_readiness_timeout_never_exposes_document_or_repeats_writes(setup_session, tmp_path, monkeypatch):
    from dwg_to_pdf.autocad import com_session as autocad
    _, app, events = setup_session
    busy = [False]
    app.GetAcadState = lambda: SimpleNamespace(IsQuiescent=not busy[0])
    app.Documents.Count = 1
    original_open = app.open
    def open_document(path, readonly):
        raw = original_open(path, readonly)
        busy[0] = True
        return raw
    app.Documents.Open = open_document
    ticks = [0.]
    def clock():
        ticks[0] += 31.
        return ticks[0]
    monkeypatch.setattr(autocad.time, "monotonic", clock)
    source = tmp_path / "source.dwg"
    source.write_bytes(b"AC1032original")
    with autocad.AutoCADSession(CadCandidate("autocad", "AutoCAD.Application.25", "clsid", Path("acad.exe"), "AutoCAD", None)) as session:
        with SourceWorkspace(source) as workspace:
            with pytest.raises(AppError) as error:
                with session.working_document(workspace):
                    pytest.fail("unready drawing must not be exposed")
            assert error.value.code == "E203"
            assert not session.is_usable
    assert len(app.opened) == 1
    assert app.closed == []
    assert app.quit_count == 1
    assert "handle-close" in events and "uninit" in events
    assert source.read_bytes() == b"AC1032original"
