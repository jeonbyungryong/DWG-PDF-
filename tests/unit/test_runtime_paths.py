from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


def test_source_runtime_paths_remain_cwd_relative(monkeypatch) -> None:
    from dwg_to_pdf import runtime_paths

    monkeypatch.setattr(runtime_paths, "sys", SimpleNamespace(frozen=False), raising=False)

    assert runtime_paths.default_config_path() == Path("config.toml")
    assert runtime_paths.default_profiles_path() == Path("template_profiles")


def test_frozen_runtime_paths_use_meipass_data_root(monkeypatch, tmp_path: Path) -> None:
    from dwg_to_pdf import runtime_paths

    monkeypatch.setattr(runtime_paths, "sys", SimpleNamespace(frozen=True, _MEIPASS=str(tmp_path)), raising=False)

    assert runtime_paths.default_config_path() == tmp_path / "config.toml"
    assert runtime_paths.default_profiles_path() == tmp_path / "template_profiles"


def test_explicit_cli_paths_remain_callers_responsibility() -> None:
    from dwg_to_pdf import runtime_paths

    explicit = Path("D:/operator/config.toml")
    assert runtime_paths.prefer_explicit(explicit, runtime_paths.default_config_path()) == explicit
