from pathlib import Path
from types import SimpleNamespace
import pytest

from dwg_to_pdf import desktop_launcher as desktop
from dwg_to_pdf.cad.selection import CadCandidate
from dwg_to_pdf.errors import AppError


def ui(provider="autocad", confirm=True, selected="AutoCAD.Application.25", config="C:/설정 파일 (A4)/autocad.toml"):
    return SimpleNamespace(choose_source_mode=lambda: "folder", choose_input_folder=lambda: "C:/input",
        choose_output_folder=lambda: "C:/output", choose_cad_provider=lambda: provider,
        confirm_experimental_autocad=lambda: confirm, choose_cad_candidate=lambda candidates: selected,
        choose_autocad_config=lambda: pytest.fail('No TOML picker'),
        show_result=lambda code: None, close=lambda: None)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch,tmp_path):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'settings'))
    monkeypatch.setattr(desktop,'prepare_autocad_config',lambda candidate:'C:/설정 파일 (A4)/autocad.toml',raising=False)


def test_gui_selection_roundtrips_to_cli(monkeypatch):
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "id", Path("C:/acad.exe"), "AutoCAD", None)
    monkeypatch.setattr(desktop, "discover_candidates", lambda provider: (candidate,), raising=False)
    calls = []
    assert desktop.run_desktop(lambda args: calls.append(args) or 0, ui=ui()) == 0
    assert calls[0][-2:] == ["--config", "C:/설정 파일 (A4)/autocad.toml"]
    assert "--allow-experimental-autocad" in calls[0]


def test_gui_provider_or_source_cancellation_never_starts(monkeypatch):
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "id", Path("C:/acad.exe"), "AutoCAD", None)
    monkeypatch.setattr(desktop, "discover_candidates", lambda provider: (candidate,), raising=False)
    calls = []
    empty_source=ui()
    empty_source.choose_input_folder=lambda:""
    for selected_ui in (ui(provider=None), empty_source):
        assert desktop.run_desktop(lambda args: calls.append(args) or 0, ui=selected_ui) == 0
    assert calls == []


def test_preparation_error_never_starts_conversion(monkeypatch):
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "id", Path("C:/acad.exe"), "AutoCAD", None)
    monkeypatch.setattr(desktop, "discover_candidates", lambda provider: (candidate,))
    selected = ui()
    results=[]
    def fail(candidate): raise AppError("E210", "setup failed")
    monkeypatch.setattr(desktop,"prepare_autocad_config",fail)
    selected.show_result=results.append
    assert desktop.run_desktop(lambda args: (_ for _ in ()).throw(AssertionError("must not convert")),ui=selected)==2
    assert results==[2]


def test_gstarcad_never_requests_autocad_config(monkeypatch):
    candidate = CadCandidate("gstarcad", "GStarCAD.Application.26", "id", Path("C:/gcad.exe"), "GstarCAD", None)
    monkeypatch.setattr(desktop, "discover_candidates", lambda provider: (candidate,))
    selected=ui(provider="gstarcad",selected=candidate.prog_id)
    selected.choose_autocad_config=lambda: (_ for _ in ()).throw(AssertionError("must not request config"))
    selected.choose_cad_candidate=lambda _: pytest.fail('Single GstarCAD installation is automatic')
    monkeypatch.setattr(desktop,'prepare_autocad_config',lambda _:pytest.fail('GstarCAD must not prepare AutoCAD'))
    calls=[]
    assert desktop.run_desktop(lambda args: calls.append(args) or 0,ui=selected)==0
    assert "--config" not in calls[0]


def test_provider_dialog_offers_autocad_without_experimental_label(monkeypatch):
    shown = []
    monkeypatch.setattr(desktop, '_message_box', lambda title, message, flags: shown.append(message) or 7)
    assert desktop.WindowsDesktopUI().choose_cad_provider() == 'autocad'
    assert 'AutoCAD' in shown[0]
    assert '실험적' not in shown[0]


def test_invalid_explicit_config_is_rejected_by_cli_before_cad(monkeypatch,tmp_path,capsys):
    from dwg_to_pdf import cli
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "id", Path("C:/acad.exe"), "AutoCAD", None)
    monkeypatch.setattr(desktop,"discover_candidates",lambda provider:(candidate,))
    monkeypatch.setattr(cli,"discover_candidates",lambda provider: (_ for _ in ()).throw(AssertionError("must not reach CAD discovery")))
    config=tmp_path/'잘못된 설정.toml'
    config.write_text('malformed[',encoding='utf-8')
    selected=ui(config=str(config))
    results=[]
    selected.show_result=results.append
    assert cli.main(["C:/input", "--output", "C:/output", "--cad", "autocad", "--allow-experimental-autocad", "--config", str(config)])==2
    assert "invalid configuration" in capsys.readouterr().err


def test_candidate_picker_encodes_untrusted_product_and_path_as_data(monkeypatch):
    import base64
    import json
    import re
    candidates = tuple(CadCandidate("autocad", f"AutoCAD.Application.{number}", str(number), Path("C:/a'; throw 'bad/acad.exe"), "AutoCAD '$()", None) for number in (25, 24))
    calls = []
    monkeypatch.setattr(desktop, "_run_picker", lambda script: calls.append(script) or ("1",))
    assert desktop.WindowsDesktopUI().choose_cad_candidate(candidates) == candidates[1].prog_id
    assert "throw 'bad" not in calls[0]
    encoded = re.search(r"FromBase64String\('([^']+)'\)", calls[0]).group(1)
    assert len(json.loads(base64.b64decode(encoded).decode("utf-8"))) == 2
