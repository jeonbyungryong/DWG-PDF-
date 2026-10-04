from dwg_to_pdf.cad.diagnostics import build_diagnostic_record, diagnostic_scope, emit
from dwg_to_pdf.cad.selection import CadCandidate
from pathlib import Path
import json


def test_diagnostics_exact_allowlist_and_unknown_version():
    record = build_diagnostic_record("autocad", "AutoCAD.Application.25", None, "test", "open", "E203")
    assert set(record) == {"provider", "prog_id", "reported_version", "app_version", "stage", "code"}
    assert record["provider"] == "autocad" and record["reported_version"] is None


def test_scope_does_not_emit_paths_or_leak_between_batches(capsys):
    candidate = CadCandidate("autocad", "AutoCAD.Application.25", "private-clsid", Path("C:/private/customer/acad.exe"), "AutoCAD", "file-version-not-COM")
    with diagnostic_scope(candidate, "test"):
        emit("start")
        emit("open", reported_version="25.0")
        emit("plot", code="E410")
    emit("outside")
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 3
    records = [json.loads(line.removeprefix("CAD_DIAGNOSTIC ")) for line in lines]
    assert records[0]["reported_version"] is None
    assert records[2]["reported_version"] == "25.0"
    assert all("private" not in line and "file-version" not in line for line in lines)
