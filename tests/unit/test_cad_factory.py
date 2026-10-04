from pathlib import Path
from types import SimpleNamespace

import pytest

from dwg_to_pdf.cad.factory import create_session, resolve_selection
from dwg_to_pdf.cad.selection import CadCandidate
from dwg_to_pdf.errors import AppError


def test_provider_override_clears_old_progid():
    config = SimpleNamespace(cad_provider="gstarcad", prog_id="GStarCAD.Application.26", allow_experimental_autocad=False)
    selected = resolve_selection(config, "autocad", None, True)
    assert selected.provider == "autocad" and selected.prog_id is None
    assert selected.allow_experimental_autocad is True


def test_config_selection_kept_without_override():
    config = SimpleNamespace(cad_provider="autocad", prog_id="AutoCAD.Application.25", allow_experimental_autocad=True)
    selected = resolve_selection(config, None, None, False)
    assert selected.provider == "autocad" and selected.prog_id == config.prog_id
    assert selected.allow_experimental_autocad


def test_factory_never_launches_or_falls_back(monkeypatch):
    from dwg_to_pdf.autocad.com_session import AutoCADSession
    from dwg_to_pdf.cad import com_session
    monkeypatch.setattr(com_session.win32com.client, "DispatchEx", lambda *args: pytest.fail("factory is CAD-free"))
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "fake", Path("C:/acad.exe"), "AutoCAD", None)
    assert isinstance(create_session(candidate), AutoCADSession)


def test_unknown_provider_is_rejected():
    candidate = CadCandidate("unknown", "unknown", "fake", Path("C:/unknown.exe"), "unknown", None)
    with pytest.raises(AppError):
        create_session(candidate)
