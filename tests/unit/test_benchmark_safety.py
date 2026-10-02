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
