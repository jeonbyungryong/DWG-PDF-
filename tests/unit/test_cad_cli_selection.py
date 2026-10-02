from types import SimpleNamespace
from pathlib import Path
import pytest

from dwg_to_pdf import cli
from dwg_to_pdf.cad.selection import CadCandidate
from dwg_to_pdf.domain import JobResult


def candidate(suffix="25"):
    return CadCandidate("autocad", "AutoCAD.Application." + suffix, suffix, Path("C:/" + suffix + "/acad.exe"), "AutoCAD", None)


@pytest.fixture
def boundary(monkeypatch, tmp_path):
    config = SimpleNamespace(cad_provider="gstarcad", prog_id="GStarCAD.Application.26", allow_experimental_autocad=False)
    monkeypatch.setattr(cli, "_preflight", lambda args: (config, (tmp_path / "source.dwg",), object(), tmp_path))
    monkeypatch.setattr(cli, "discover_candidates", lambda provider: (candidate(),))
    monkeypatch.setattr(cli, "_conversion_dependencies", lambda: (lambda *args: object(), lambda selected: selected, lambda *args: (JobResult(tmp_path / "source.dwg", "success", ()),)))
    return ["source.dwg", "--output", str(tmp_path), "--cad", "autocad"]


def test_autocad_requires_opt_in_before_start(boundary, capsys):
    assert cli.main(boundary) == 2
    assert "E222" in capsys.readouterr().err


def test_opt_in_warning_before_start(boundary, capsys):
    assert cli.main([*boundary, "--allow-experimental-autocad"]) == 0
    assert "실험적" in capsys.readouterr().err


def test_ambiguous_candidate_noninteractive_rejected(boundary, monkeypatch, capsys):
    monkeypatch.setattr(cli, "discover_candidates", lambda provider: (candidate(), candidate("24")))
    assert cli.main([*boundary, "--allow-experimental-autocad"]) == 2
    assert "E221" in capsys.readouterr().err


def test_list_cad_does_not_launch_or_load_configuration(monkeypatch, capsys):
    monkeypatch.setattr(cli, "discover_candidates", lambda provider: (candidate(),) if provider == "autocad" else ())
    monkeypatch.setattr(cli, "load_config", lambda *args: pytest.fail("list is read-only"))
    monkeypatch.setattr(cli, "_conversion_dependencies", lambda: pytest.fail("list never loads COM"))
    assert cli.main(["--list-cad"]) == 0
    assert "AutoCAD.Application.25" in capsys.readouterr().out


def test_autocad_failure_never_starts_gstarcad(boundary, monkeypatch):
    from dwg_to_pdf.orchestrator import run_jobs
    from dwg_to_pdf.errors import AppError
    calls = []
    class FailedSession:
        def __enter__(self): raise AppError("E201", "synthetic AutoCAD startup failure")
        def __exit__(self, *args): pass
    def factory(selected):
        calls.append(selected.provider)
        return FailedSession()
    monkeypatch.setattr(cli, "_conversion_dependencies", lambda: (lambda *args: object(), factory, run_jobs))
    assert cli.main([*boundary, "--allow-experimental-autocad"]) == 1
    assert calls == ["autocad"]
