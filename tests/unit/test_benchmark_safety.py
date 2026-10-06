import importlib.util
from pathlib import Path


def benchmark():
    path = Path(__file__).parents[2] / "tools" / "benchmark_conversion.py"
    spec = importlib.util.spec_from_file_location("performance_benchmark", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def result(before, after):
    return {"outcomes": [{"source": "part.dwg"}], "sources_unchanged": True, "owned_pid_closed": True, "user_pids_before": before, "user_pids_after": after}


def test_benchmark_fails_when_a_preexisting_cad_process_disappears():
    assert benchmark().benchmark_passed(result([100, 200], [100])) is False


def test_benchmark_accepts_preserved_cad_and_new_unrelated_process():
    assert benchmark().benchmark_passed(result([100], [100, 200])) is True


def test_benchmark_never_claims_success_for_no_inputs_or_a_conversion_error():
    data = result([], [])
    data["outcomes"] = []
    assert benchmark().benchmark_passed(data) is False
    data["outcomes"] = [{"error": "conversion failed"}]
    assert benchmark().benchmark_passed(data) is False


def test_benchmark_uses_selected_config_provider_without_starting_cad(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from dwg_to_pdf.cad.selection import CadCandidate
    import dwg_to_pdf.configuration as configuration
    import dwg_to_pdf.cad.discovery as discovery
    import dwg_to_pdf.cad.factory as factory
    config = SimpleNamespace(cad_provider="autocad", prog_id="AutoCAD.Application.25", allow_experimental_autocad=True)
    selected = CadCandidate("autocad", config.prog_id, "id", tmp_path / "acad.exe", "AutoCAD", None)
    paths, candidates = [], []
    monkeypatch.setattr(configuration, "load_config", lambda path: paths.append(path) or config)
    monkeypatch.setattr(discovery, "discover_candidates", lambda provider: (selected,) if provider == "autocad" else ())
    monkeypatch.setattr(factory, "create_session", lambda candidate: candidates.append(candidate) or object())
    explicit = tmp_path / "operator.toml"
    received, candidate, session = benchmark().prepare_session(tmp_path, explicit)
    assert paths == [explicit] and candidates == [selected]
    assert received is config and candidate.provider == "autocad"


def test_gstar_baseline_validation_supports_pre_autocad_signature(monkeypatch, tmp_path):
    import dwg_to_pdf.pdf_validator as validator
    calls = []
    def old_validate(path):
        calls.append(path)
        return "valid"
    monkeypatch.setattr(validator, "validate_pdf", old_validate)
    path = tmp_path / "out.pdf"
    assert benchmark().validate_output(path, "gstarcad") == "valid"
    assert calls == [path]
