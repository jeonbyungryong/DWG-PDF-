import importlib.util
from pathlib import Path

import pytest

from dwg_to_pdf.configuration import load_config

ROOT = Path(__file__).parents[2]


def test_default_provider_remains_gstarcad():
    assert load_config(ROOT / "config.toml").cad_provider == "gstarcad"
    assert not load_config(ROOT / "config.toml").allow_experimental_autocad


def test_live_autocad_requires_opt_in_environment():
    from dwg_to_pdf.cad.validation import live_autocad_environment
    for env in ({}, {"AUTOCAD_TEST_ENABLED": "1"}, {"AUTOCAD_TEST_ENABLED": "0", "AUTOCAD_TEST_CONFIG": "x", "AUTOCAD_TEST_DWGS": "y"}):
        with pytest.raises(ValueError):
            live_autocad_environment(env)
    config, dwgs = live_autocad_environment({"AUTOCAD_TEST_ENABLED": "1", "AUTOCAD_TEST_CONFIG": "C:/config.toml", "AUTOCAD_TEST_DWGS": "C:/a.dwg;C:/b.dwg"})
    assert config == Path("C:/config.toml") and len(dwgs) == 2


def test_frozen_smoke_passes_config_explicitly(tmp_path):
    spec = importlib.util.spec_from_file_location("smoke", ROOT / "tools/smoke_frozen_bundle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = tmp_path / "실험 설정.toml"
    config.write_text("# test", encoding="utf-8")
    command = module.build_command(Path("C:/app.exe"), [Path("C:/a.dwg")], Path("C:/out"), config)
    assert command[-2:] == ["--config", str(config.resolve())]
    assert "--config" not in module.build_command(Path("C:/app.exe"), [], Path("C:/out"), None)


def test_live_cleanup_gate_checks_captured_pid_not_cleared_field():
    from dwg_to_pdf.cad.validation import require_process_cleanup
    from types import SimpleNamespace
    session = SimpleNamespace(owned_pid=None)
    with pytest.raises(AssertionError):
        require_process_cleanup({10}, {71}, {10, 71})
    require_process_cleanup({10}, {71}, {10})
    assert session.owned_pid is None
