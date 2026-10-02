from pathlib import Path
from types import SimpleNamespace

from dwg_to_pdf import desktop_launcher as desktop
from dwg_to_pdf.cad.selection import CadCandidate


def ui(provider="autocad", confirm=True, selected="AutoCAD.Application.25"):
    return SimpleNamespace(choose_source_mode=lambda: "folder", choose_input_folder=lambda: "C:/input",
        choose_output_folder=lambda: "C:/output", choose_cad_provider=lambda: provider,
        confirm_experimental_autocad=lambda: confirm, choose_cad_candidate=lambda candidates: selected,
        show_result=lambda code: None, close=lambda: None)


def test_gui_selection_roundtrips_to_cli(monkeypatch):
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "id", Path("C:/acad.exe"), "AutoCAD", None)
    monkeypatch.setattr(desktop, "discover_candidates", lambda provider: (candidate,), raising=False)
    calls = []
    assert desktop.run_desktop(lambda args: calls.append(args) or 0, ui=ui()) == 0
    assert calls[0][-5:] == ["--cad", "autocad", "--cad-prog-id", candidate.prog_id, "--allow-experimental-autocad"]


def test_gui_cancellation_or_declined_experiment_never_starts(monkeypatch):
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "id", Path("C:/acad.exe"), "AutoCAD", None)
    monkeypatch.setattr(desktop, "discover_candidates", lambda provider: (candidate,), raising=False)
    calls = []
    for selected_ui in (ui(provider=None), ui(confirm=False), ui(selected=None)):
        assert desktop.run_desktop(lambda args: calls.append(args) or 0, ui=selected_ui) == 0
    assert calls == []


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
