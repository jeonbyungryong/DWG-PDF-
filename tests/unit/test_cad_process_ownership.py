from datetime import datetime, timezone
from pathlib import Path

import pytest

from dwg_to_pdf.cad import process_ownership as ownership
from dwg_to_pdf.cad.selection import CadCandidate
from dwg_to_pdf.errors import AppError


@pytest.fixture
def boundary(monkeypatch, tmp_path):
    executable = tmp_path / "acad.exe"
    executable.write_bytes(b"fake")
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "clsid", executable, "AutoCAD", None)
    handle = object()
    events = []
    created = datetime.now(timezone.utc)
    monkeypatch.setattr(ownership, "_window_pid", lambda hwnd: 71)
    monkeypatch.setattr(ownership, "_product_pids", lambda candidate: frozenset({71}))
    monkeypatch.setattr(ownership, "_open_process", lambda pid: handle)
    monkeypatch.setattr(ownership, "_identity", lambda h: (71, executable.resolve(), created))
    monkeypatch.setattr(ownership, "_running", lambda h: True)
    monkeypatch.setattr(ownership, "_close_handle", lambda h: events.append(("close", h)))
    monkeypatch.setattr(ownership, "_terminate", lambda h: events.append(("terminate", h)))
    return candidate, handle, events


def test_pid_reuse_never_terminates_replacement(boundary):
    candidate, handle, events = boundary
    process = ownership.capture_owned_process(candidate, 123, frozenset({1}), frozenset({1, 71}))
    process.terminate_if_running()
    process.close()
    process.close()
    assert events == [("terminate", handle), ("close", handle)]


@pytest.mark.parametrize("before,after", [({71}, {71}), (set(), set()), ({1}, {1, 71, 72})])
def test_existing_missing_or_extra_product_process_rejected(boundary, monkeypatch, before, after):
    candidate, _, events = boundary
    monkeypatch.setattr(ownership, "_product_pids", lambda _: frozenset({71, 72}))
    with pytest.raises(AppError) as error:
        ownership.capture_owned_process(candidate, 123, frozenset(before), frozenset(after))
    assert error.value.code == "E201"
    assert events == []


def test_executable_mismatch_rejected(boundary, monkeypatch):
    candidate, handle, events = boundary
    monkeypatch.setattr(ownership, "_identity", lambda _: (71, Path("C:/other/acad.exe"), datetime.now(timezone.utc)))
    with pytest.raises(AppError):
        ownership.capture_owned_process(candidate, 123, frozenset(), frozenset({71}))
    assert events == [("close", handle)]


def test_window_identity_change_rejected(boundary, monkeypatch):
    candidate, handle, events = boundary
    pids = iter((71, 72))
    monkeypatch.setattr(ownership, "_window_pid", lambda _: next(pids))
    with pytest.raises(AppError):
        ownership.capture_owned_process(candidate, 123, frozenset(), frozenset({71}))
    assert events == [("close", handle)]


def test_process_created_before_dispatch_rejected(boundary, monkeypatch):
    candidate, handle, events = boundary
    with pytest.raises(AppError):
        ownership.capture_owned_process(candidate, 123, frozenset(), frozenset({71}), started_at=datetime(2100, 1, 1, tzinfo=timezone.utc))
    assert events == [("close", handle)]


def test_handle_capture_failure_never_terminates(boundary, monkeypatch):
    candidate, _, events = boundary
    monkeypatch.setattr(ownership, "_open_process", lambda _: (_ for _ in ()).throw(OSError("denied")))
    with pytest.raises(AppError) as error:
        ownership.capture_owned_process(candidate, 123, frozenset(), frozenset({71}))
    assert error.value.code == "E201"
    assert events == []


def test_current_process_identity_read_only():
    import os
    import sys
    handle = ownership._open_process(os.getpid())
    try:
        pid, executable, created = ownership._identity(handle)
        assert pid == os.getpid()
        assert executable.samefile(sys.executable)
        assert created <= datetime.now(timezone.utc)
    finally:
        ownership._close_handle(handle)
