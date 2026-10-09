from pathlib import Path
from types import SimpleNamespace

from dwg_to_pdf import desktop_launcher as desktop
from dwg_to_pdf.cad.selection import CadCandidate


def ui(provider="autocad", confirm=True, selected="AutoCAD.Application.25", config="C:/설정 파일 (A4)/autocad.toml"):
    return SimpleNamespace(choose_source_mode=lambda: "folder", choose_input_folder=lambda: "C:/input",
        choose_output_folder=lambda: "C:/output", choose_cad_provider=lambda: provider,
        confirm_experimental_autocad=lambda: confirm, choose_cad_candidate=lambda candidates: selected,
        choose_autocad_config=lambda: config,
        show_result=lambda code: None, close=lambda: None)


def test_gui_selection_roundtrips_to_cli(monkeypatch):
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "id", Path("C:/acad.exe"), "AutoCAD", None)
    monkeypatch.setattr(desktop, "discover_candidates", lambda provider: (candidate,), raising=False)
    calls = []
    assert desktop.run_desktop(lambda args: calls.append(args) or 0, ui=ui()) == 0
    assert calls[0][-2:] == ["--config", "C:/설정 파일 (A4)/autocad.toml"]
    assert "--allow-experimental-autocad" in calls[0]


def test_gui_cancellation_or_declined_experiment_never_starts(monkeypatch):
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "id", Path("C:/acad.exe"), "AutoCAD", None)
    monkeypatch.setattr(desktop, "discover_candidates", lambda provider: (candidate,), raising=False)
    calls = []
    for selected_ui in (ui(provider=None), ui(confirm=False), ui(selected=None), ui(config="")):
        assert desktop.run_desktop(lambda args: calls.append(args) or 0, ui=selected_ui) == 0
    assert calls == []


def test_config_dialog_error_never_starts_conversion(monkeypatch):
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "id", Path("C:/acad.exe"), "AutoCAD", None)
    monkeypatch.setattr(desktop, "discover_candidates", lambda provider: (candidate,))
    selected = ui()
    results=[]
    def fail(): raise OSError("config picker failed")
    selected.choose_autocad_config=fail
    selected.show_result=results.append
    assert desktop.run_desktop(lambda args: (_ for _ in ()).throw(AssertionError("must not convert")),ui=selected)==2
    assert results==[2]


def test_gstarcad_never_requests_autocad_config(monkeypatch):
    candidate = CadCandidate("gstarcad", "GStarCAD.Application.26", "id", Path("C:/gcad.exe"), "GstarCAD", None)
    monkeypatch.setattr(desktop, "discover_candidates", lambda provider: (candidate,))
    selected=ui(provider="gstarcad",selected=candidate.prog_id)
    selected.choose_autocad_config=lambda: (_ for _ in ()).throw(AssertionError("must not request config"))
    calls=[]
    assert desktop.run_desktop(lambda args: calls.append(args) or 0,ui=selected)==0
    assert "--config" not in calls[0]


def test_invalid_selected_config_is_rejected_by_cli_before_cad(monkeypatch,tmp_path,capsys):
    from dwg_to_pdf import cli
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "id", Path("C:/acad.exe"), "AutoCAD", None)
    monkeypatch.setattr(desktop,"discover_candidates",lambda provider:(candidate,))
    monkeypatch.setattr(cli,"discover_candidates",lambda provider: (_ for _ in ()).throw(AssertionError("must not reach CAD discovery")))
    config=tmp_path/'잘못된 설정.toml'
    config.write_text('malformed[',encoding='utf-8')
    selected=ui(config=str(config))
    results=[]
    selected.show_result=results.append
    assert desktop.run_desktop(cli.main,ui=selected)==2
    assert results==[2]
    assert "invalid configuration" in capsys.readouterr().err


def test_windows_config_picker_returns_one_path(monkeypatch):
    monkeypatch.setattr(desktop,"pick_config_file",lambda title:"D:/설정/autocad.toml",raising=False)
    assert desktop.WindowsDesktopUI().choose_autocad_config()=="D:/설정/autocad.toml"


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
