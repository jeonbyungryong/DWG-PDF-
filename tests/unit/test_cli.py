from __future__ import annotations

import builtins
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from dwg_to_pdf.domain import JobResult
from dwg_to_pdf.errors import AppError


def _install_happy_preflight(monkeypatch, cli, tmp_path: Path):
    config = SimpleNamespace(prog_id="GstarCAD.Application.26")
    source = tmp_path / "input.dwg"
    source.write_bytes(b"dwg")
    profile_directory = tmp_path / "profiles"
    profile_directory.mkdir()
    calls: dict[str, object] = {}

    class FakeStore:
        def __init__(self, directory: Path, *, source_root: Path) -> None:
            calls["store"] = (directory, source_root)

        def load_all(self) -> None:
            calls["profiles_loaded"] = True

        def all(self) -> tuple[object, ...]:
            return ()

    monkeypatch.setattr(cli, "load_config", lambda path: calls.setdefault("config", path) and config)
    monkeypatch.setattr(cli, "resolve_inputs", lambda paths: calls.setdefault("inputs", paths) and (source,))
    monkeypatch.setattr(cli, "ProfileStore", FakeStore)
    monkeypatch.setattr(cli, "require_canonical_profiles", lambda profiles: profiles)
    monkeypatch.setattr(cli, "ConversionService", lambda received_config, profiles: (received_config, profiles))
    return config, source, profile_directory, calls


def test_main_preflights_then_calls_run_jobs_once_with_gstar_session_factory(monkeypatch, tmp_path: Path) -> None:
    from dwg_to_pdf import cli

    config, source, profile_directory, calls = _install_happy_preflight(monkeypatch, cli, tmp_path)
    output = tmp_path / "nested" / "output"
    factories: list[object] = []

    class FakeSession:
        def __init__(self, prog_id: str) -> None:
            self.prog_id = prog_id

    def fake_run_jobs(service, sources, output_dir, conflict_policy, session_factory):
        calls["run_jobs"] = (service, sources, output_dir, conflict_policy)
        created = session_factory()
        factories.append(created)
        return (JobResult(source, "success", (output / "input.pdf",)),)

    monkeypatch.setattr(cli, "GstarSession", FakeSession)
    monkeypatch.setattr(cli, "run_jobs", fake_run_jobs)
    monkeypatch.setattr(
        cli,
        "build_result_report",
        lambda results: SimpleNamespace(summary_text="변환 결과: 전체 1건 / 성공 1건 / 실패 0건 / 건너뜀 0건"),
    )

    assert cli.main([str(source), "--output", str(output), "--profiles", str(profile_directory), "--conflict", "copy"]) == 0
    assert calls["config"] == Path("config.toml")
    assert calls["store"] == (profile_directory, profile_directory)
    assert calls["profiles_loaded"] is True
    service, sources, received_output, policy = calls["run_jobs"]
    assert service[0] is config
    assert sources == (source,)
    assert received_output == output
    assert policy == "copy"
    assert len(factories) == 1
    assert isinstance(factories[0], FakeSession)
    assert factories[0].prog_id == config.prog_id
    assert output.is_dir()


def test_main_uses_explicit_template_source_root(monkeypatch, tmp_path: Path) -> None:
    from dwg_to_pdf import cli

    _config, source, profile_directory, calls = _install_happy_preflight(monkeypatch, cli, tmp_path)
    root = tmp_path / "reference-dwgs"
    root.mkdir()
    monkeypatch.setattr(cli, "run_jobs", lambda *_args: ())
    monkeypatch.setattr(cli, "build_result_report", lambda _results: SimpleNamespace(summary_text="완료"))

    assert cli.main(
        [str(source), "--output", str(tmp_path / "output"), "--profiles", str(profile_directory), "--template-source-root", str(root)]
    ) == 0
    assert calls["store"] == (profile_directory, root)


@pytest.mark.parametrize("status, expected", [("success", 0), ("failed", 1), ("skipped", 1)])
def test_main_exit_code_reflects_final_job_statuses(monkeypatch, tmp_path: Path, status: str, expected: int) -> None:
    from dwg_to_pdf import cli

    _config, source, profile_directory, _calls = _install_happy_preflight(monkeypatch, cli, tmp_path)
    monkeypatch.setattr(cli, "run_jobs", lambda *_args: (JobResult(source, status, ()),))
    monkeypatch.setattr(cli, "build_result_report", lambda _results: SimpleNamespace(summary_text="요약"))

    assert cli.main([str(source), "--output", str(tmp_path / "output"), "--profiles", str(profile_directory)]) == expected


def test_main_preflight_error_prints_stderr_once_and_never_starts_batch(monkeypatch, tmp_path: Path, capsys) -> None:
    from dwg_to_pdf import cli

    called = {"run_jobs": False, "factory": False}
    monkeypatch.setattr(cli, "load_config", lambda _path: (_ for _ in ()).throw(AppError("E001", "bad configuration")))
    monkeypatch.setattr(cli, "run_jobs", lambda *_args: called.__setitem__("run_jobs", True))
    monkeypatch.setattr(cli, "GstarSession", lambda _prog_id: called.__setitem__("factory", True))

    assert cli.main([str(tmp_path / "input.dwg"), "--output", str(tmp_path / "output")]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("E001") == 1
    assert "초기화 실패" in captured.err
    assert called == {"run_jobs": False, "factory": False}


def test_main_output_preparation_failure_returns_two_without_session_or_batch(monkeypatch, tmp_path: Path, capsys) -> None:
    from dwg_to_pdf import cli

    config, source, profile_directory, _calls = _install_happy_preflight(monkeypatch, cli, tmp_path)
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("occupied", encoding="utf-8")
    called = {"run_jobs": False, "factory": False}
    monkeypatch.setattr(cli, "run_jobs", lambda *_args: called.__setitem__("run_jobs", True))
    monkeypatch.setattr(cli, "GstarSession", lambda _prog_id: called.__setitem__("factory", True))

    assert cli.main([str(source), "--output", str(output_file), "--profiles", str(profile_directory)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("E001") == 1
    assert "초기화 실패" in captured.err
    assert config.prog_id
    assert called == {"run_jobs": False, "factory": False}


def test_incomplete_canonical_profile_set_fails_before_session_or_batch(monkeypatch, tmp_path: Path, capsys) -> None:
    from dwg_to_pdf import cli
    from dwg_to_pdf.templates.profile_store import require_canonical_profiles

    _config, source, profile_directory, _calls = _install_happy_preflight(monkeypatch, cli, tmp_path)
    called = {"run_jobs": False, "factory": False}

    class IncompleteStore:
        def __init__(self, _directory: Path, *, source_root: Path) -> None:
            self.source_root = source_root

        def load_all(self) -> None:
            pass

        def all(self) -> tuple[object, ...]:
            return ()

    monkeypatch.setattr(cli, "ProfileStore", IncompleteStore)
    monkeypatch.setattr(cli, "require_canonical_profiles", require_canonical_profiles)
    monkeypatch.setattr(cli, "run_jobs", lambda *_args: called.__setitem__("run_jobs", True))
    monkeypatch.setattr(cli, "GstarSession", lambda _prog_id: called.__setitem__("factory", True))

    assert cli.main([str(source), "--output", str(tmp_path / "output"), "--profiles", str(profile_directory)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "초기화 실패" in captured.err
    assert "E300" in captured.err
    assert called == {"run_jobs": False, "factory": False}


def test_main_prints_one_summary_without_log_detail(monkeypatch, tmp_path: Path) -> None:
    from dwg_to_pdf import cli

    _config, source, profile_directory, _calls = _install_happy_preflight(monkeypatch, cli, tmp_path)
    results = (JobResult(source, "failed", (), "E303", "사용자용 사유", "internal COM trace"),)
    monkeypatch.setattr(cli, "run_jobs", lambda *_args: results)
    summary = "변환 결과: 전체 1건 / 성공 0건 / 실패 1건 / 건너뜀 0건\ninput.dwg파일의 변환이 실패하였습니다(사유 : 사용자용 사유)"
    monkeypatch.setattr(cli, "build_result_report", lambda _results: SimpleNamespace(summary_text=summary))
    printed: list[tuple[object, ...]] = []
    monkeypatch.setattr(builtins, "print", lambda *args, **_kwargs: printed.append(args))

    assert cli.main([str(source), "--output", str(tmp_path / "output"), "--profiles", str(profile_directory)]) == 1
    assert printed == [(summary,)]
    assert "internal COM trace" not in str(printed)


def test_main_without_arguments_opens_desktop_launcher(monkeypatch) -> None:
    from dwg_to_pdf import cli

    monkeypatch.setattr(cli, "_launch_desktop", lambda: 7)

    assert cli.main([]) == 7


def test_bad_argparse_contract_raises_standard_systemexit() -> None:
    from dwg_to_pdf import cli

    with pytest.raises(SystemExit):
        cli.main(["drawing.dwg", "--output", "out", "--conflict", "invalid"])


def test_self_check_uses_default_resources_and_imports_conversion_dependencies_without_starting_a_session(monkeypatch, tmp_path: Path, capsys) -> None:
    from dwg_to_pdf import cli

    config_path = tmp_path / "config.toml"
    profiles_path = tmp_path / "template_profiles"
    profiles_path.mkdir()
    calls: dict[str, object] = {}

    class FakeStore:
        def __init__(self, directory, *, source_root) -> None:
            calls["store"] = (directory, source_root)

        def load_all(self) -> None:
            calls["loaded"] = True

        def all(self) -> tuple[object, ...]:
            return ()

    monkeypatch.setattr(cli, "default_config_path", lambda: config_path)
    monkeypatch.setattr(cli, "default_profiles_path", lambda: profiles_path)
    monkeypatch.setattr(cli, "load_config", lambda path: calls.setdefault("config", path))
    monkeypatch.setattr(cli, "ProfileStore", FakeStore)
    monkeypatch.setattr(cli, "require_canonical_profiles", lambda profiles: calls.setdefault("canonical", profiles))
    monkeypatch.setattr(cli, "_conversion_dependencies", lambda: calls.setdefault("dependencies", (object(), object(), object())))

    assert cli.main(["--self-check"]) == 0
    assert capsys.readouterr().out == "RUNTIME_SELF_CHECK_OK\n"
    assert calls["config"] == config_path
    assert calls["store"] == (profiles_path, profiles_path)
    assert calls["loaded"] is True
    assert calls["canonical"] == ()
    assert "dependencies" in calls


def test_self_check_honors_explicit_config_profiles_and_source_root(monkeypatch, tmp_path: Path, capsys) -> None:
    from dwg_to_pdf import cli

    config = tmp_path / "operator.toml"
    profiles = tmp_path / "profiles"
    source_root = tmp_path / "reference"
    profiles.mkdir(); source_root.mkdir()
    calls = {}
    class Store:
        def __init__(self, directory, *, source_root): calls["store"] = (directory, source_root)
        def load_all(self): pass
        def all(self): return ()
    monkeypatch.setattr(cli, "load_config", lambda path: calls.setdefault("config", path))
    monkeypatch.setattr(cli, "ProfileStore", Store)
    monkeypatch.setattr(cli, "require_canonical_profiles", lambda _profiles: None)
    monkeypatch.setattr(cli, "_conversion_dependencies", lambda: calls.setdefault("deps", (object(), object(), object())))
    assert cli.main(["--self-check", "--config", str(config), "--profiles", str(profiles), "--template-source-root", str(source_root)]) == 0
    assert calls["config"] == config
    assert calls["store"] == (profiles, source_root)
    assert capsys.readouterr().out == "RUNTIME_SELF_CHECK_OK\n"


def test_importing_main_module_has_no_execution_side_effect(monkeypatch) -> None:
    from dwg_to_pdf import cli

    monkeypatch.setattr(cli, "main", lambda: (_ for _ in ()).throw(AssertionError("must not execute on import")))
    module = importlib.import_module("dwg_to_pdf.__main__")

    assert module is not None


def test_cli_source_has_no_direct_process_or_scale_filename_heuristics() -> None:
    from dwg_to_pdf import cli

    source = Path(cli.__file__).read_text(encoding="utf-8").casefold()
    for forbidden in ("taskkill", "_gstar_pids", "filename scale", "dialog"):
        assert forbidden not in source
