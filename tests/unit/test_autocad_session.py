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
    source.write_bytes(b"original")
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
    assert source.read_bytes() == b"original"
    assert "handle-close" in events


def test_wrong_document_identity_rejected(setup_session, tmp_path):
    session, app, _ = setup_session
    source = tmp_path / "source.dwg"
    source.write_bytes(b"original")
    app.Documents.Open = lambda *args: SimpleNamespace(ReadOnly=False, FullName=str(source), Close=lambda save: app.closed.append(save))
    with session, SourceWorkspace(source) as workspace:
        with pytest.raises(AppError) as error:
            with session.working_document(workspace):
                pytest.fail("must not expose wrong drawing")
        assert error.value.code == "E203"
    assert app.closed == [False]
