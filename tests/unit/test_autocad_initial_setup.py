from contextlib import contextmanager
import hashlib
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from dwg_to_pdf.cad.selection import CadCandidate
from dwg_to_pdf.configuration import load_config
from dwg_to_pdf.errors import AppError
from dwg_to_pdf.temp_workspace import SourceWorkspace


PREFERRED = "ISO_full_bleed_A4_(297.00_x_210.00_MM)"
PROFILES = Path(__file__).resolve().parents[2] / "packaging/bundle-assets/template_profiles"


class Layout:
    ConfigName = ""
    CanonicalMediaName = ""

    def __init__(self):
        self.devices = ("DWG To PDF.pc3",)
        self.styles = ("monochrome.ctb",)
        self.sizes = {PREFERRED: (297., 210.)}

    def RefreshPlotDeviceInfo(self):
        pass

    def GetPlotDeviceNames(self):
        return self.devices

    def GetPlotStyleTableNames(self):
        return self.styles

    def GetCanonicalMediaNames(self):
        return tuple(self.sizes)

    def GetPaperSize(self):
        return self.sizes[self.CanonicalMediaName]


def setup_environment(monkeypatch, tmp_path):
    initial = importlib.import_module("dwg_to_pdf.autocad.initial_setup")
    root = tmp_path / "사용자 설정 (A4)"
    monkeypatch.setenv("LOCALAPPDATA", str(root))
    pc3 = tmp_path / "AutoCAD 플로터" / "DWG To PDF.pc3"
    pc3.parent.mkdir()
    pc3.write_bytes(b"installed PC3")
    layout = Layout()
    candidate = CadCandidate("autocad", "AutoCAD.Application.24", "id", tmp_path / "acad.exe", "AutoCAD", "24.0")
    events = []
    app = SimpleNamespace(Preferences=SimpleNamespace(Files=SimpleNamespace(PrinterConfigPath=str(pc3.parent))))

    class Session:
        _owned_process_handle = 42

        def __init__(self, selected):
            assert selected == candidate
            self.app = app

        def __enter__(self):
            events.append("owned_session_open")
            return self

        def __exit__(self, *args):
            events.append("owned_session_close")

        @contextmanager
        def working_document(self, workspace):
            copy = workspace.authorized_copy()
            assert copy != workspace.source and copy.read_bytes() == workspace.source.read_bytes()
            events.append("copy_open")
            try:
                yield SimpleNamespace(raw=SimpleNamespace(ActiveLayout=layout))
            finally:
                events.append("copy_close")

    monkeypatch.setitem(sys.modules, "dwg_to_pdf.autocad.com_session", SimpleNamespace(AutoCADSession=Session))
    monkeypatch.setitem(sys.modules, "win32api", SimpleNamespace(
        GetCurrentProcess=lambda: 1,
        DuplicateHandle=lambda current, handle, target, access, inherit, options:
            events.append(("duplicate", handle, access)) or 43,
        CloseHandle=lambda handle: events.append(("handle_close", handle)),
    ))
    monkeypatch.setitem(sys.modules, "win32event", SimpleNamespace(
        WaitForSingleObject=lambda handle, timeout: events.append(("wait", handle, timeout)) or 0,
    ))
    monkeypatch.setattr(initial, "default_profiles_path", lambda: PROFILES)
    monkeypatch.setattr(initial, "SourceWorkspace", lambda source: SourceWorkspace(source, temp_root=tmp_path))
    return SimpleNamespace(initial=initial, root=root, pc3=pc3, layout=layout,
                           candidate=candidate, app=app, events=events, session=Session)


def test_prepare_config_roundtrips_fixed_policy(monkeypatch, tmp_path):
    env = setup_environment(monkeypatch, tmp_path)
    before = (env.pc3.read_bytes(), env.pc3.stat().st_mtime_ns)
    config_path = Path(env.initial.prepare_autocad_config(env.candidate))
    config = load_config(config_path)
    assert config_path.is_relative_to(env.root / "DWG-to-PDF/autocad-auto")
    assert config.cad_provider == "autocad"
    assert config.prog_id == "AutoCAD.Application.24"
    assert config.allow_experimental_autocad is True
    assert config.auto_match_enabled is True and config.use_native_extraction is True
    assert (config.matching_threshold, config.minimum_score_gap) == (1., 1.)
    assert (config.media_width_mm, config.media_height_mm) == (297., 210.)
    assert config.style_sheet == "monochrome.ctb"
    assert config.preferred_media_names == (PREFERRED,)
    assert config.autocad_pc3_path.is_absolute() and config.autocad_pc3_path != env.pc3
    assert config.autocad_pc3_path.read_bytes() == before[0]
    assert (env.pc3.read_bytes(), env.pc3.stat().st_mtime_ns) == before
    assert env.events.index("owned_session_close") < env.events.index(("wait", 43, 30000))
    assert ("duplicate", 42, 0x00100000) in env.events
    assert env.events[-1] == ("handle_close", 43)
    assert not (env.root / "DWG-to-PDF/autocad-settings.json").exists()


@pytest.mark.parametrize("case", ["missing", "distinct"])
def test_missing_or_distinct_pc3_candidates_fail(monkeypatch, tmp_path, case):
    env = setup_environment(monkeypatch, tmp_path)
    if case == "missing":
        env.pc3.unlink()
    else:
        other = tmp_path / "second"
        other.mkdir()
        (other / "DWG To PDF.pc3").write_bytes(env.pc3.read_bytes())
        env.app.Preferences.Files.PrinterConfigPath += ";" + str(other)
    with pytest.raises(AppError) as raised:
        env.initial.prepare_autocad_config(env.candidate)
    assert raised.value.code == "E210"
    assert "copy_open" not in env.events
    assert env.events[-1] == ("handle_close", 43)
    assert not (env.root / "DWG-to-PDF/autocad-auto").exists()


def test_duplicate_paths_to_same_pc3_are_deduplicated(monkeypatch, tmp_path):
    env = setup_environment(monkeypatch, tmp_path)
    env.app.Preferences.Files.PrinterConfigPath += ";" + str(env.pc3.parent / ".")
    assert Path(env.initial.prepare_autocad_config(env.candidate)).is_file()


@pytest.mark.parametrize("kind,code", [("device", "E210"), ("ctb", "E212")])
def test_missing_plot_environment_fails(monkeypatch, tmp_path, kind, code):
    env = setup_environment(monkeypatch, tmp_path)
    if kind == "device":
        env.layout.devices = ()
    else:
        env.layout.styles = ()
    with pytest.raises(AppError) as raised:
        env.initial.prepare_autocad_config(env.candidate)
    assert raised.value.code == code
    assert env.events.index("copy_close") < env.events.index("owned_session_close")
    assert not (env.root / "DWG-to-PDF/autocad-auto").exists()


@pytest.mark.parametrize("sizes", [
    {PREFERRED: (420., 297.)}, {PREFERRED: (float("nan"), 210.)},
    {"A4 one": (210., 297.), "A4 two": (297., 210.)}, {},
])
def test_invalid_or_ambiguous_a4_fails(monkeypatch, tmp_path, sizes):
    env = setup_environment(monkeypatch, tmp_path)
    env.layout.sizes = sizes
    with pytest.raises(AppError) as raised:
        env.initial.prepare_autocad_config(env.candidate)
    assert raised.value.code == "E211"


def test_unique_measured_portrait_a4_is_accepted(monkeypatch, tmp_path):
    env = setup_environment(monkeypatch, tmp_path)
    env.layout.sizes = {"현지 A4 이름": (210., 297.)}
    config = load_config(Path(env.initial.prepare_autocad_config(env.candidate)))
    assert config.preferred_media_names == ("현지 A4 이름",)
    assert (config.media_width_mm, config.media_height_mm) == (297., 210.)


def test_failed_write_removes_only_owned_partial_files(monkeypatch, tmp_path):
    env = setup_environment(monkeypatch, tmp_path)
    existing = env.root / "DWG-to-PDF/autocad-auto/previous"
    existing.mkdir(parents=True)
    kept = existing / "custom.toml"
    kept.write_bytes(b"existing settings")
    before = (kept.read_bytes(), kept.stat().st_mtime_ns)
    original = Path.write_text

    def fail_config(path, *args, **kwargs):
        if path.name == "AutoCAD.toml":
            raise PermissionError("read-only destination")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_config)
    with pytest.raises(AppError):
        env.initial.prepare_autocad_config(env.candidate)
    assert list(existing.parent.iterdir()) == [existing]
    assert (kept.read_bytes(), kept.stat().st_mtime_ns) == before
    assert env.pc3.read_bytes() == b"installed PC3"


def test_pc3_change_during_preparation_is_rejected(monkeypatch, tmp_path):
    env = setup_environment(monkeypatch, tmp_path)
    original = env.layout.GetCanonicalMediaNames

    def mutate():
        env.pc3.write_bytes(b"externally changed PC3")
        return original()

    env.layout.GetCanonicalMediaNames = mutate
    with pytest.raises(AppError) as raised:
        env.initial.prepare_autocad_config(env.candidate)
    assert raised.value.code == "E210"
    assert not (env.root / "DWG-to-PDF/autocad-auto").exists()


def test_pc3_change_after_inspection_is_rejected(monkeypatch, tmp_path):
    env = setup_environment(monkeypatch, tmp_path)
    digest = hashlib.sha256(env.pc3.read_bytes()).hexdigest()
    env.pc3.write_bytes(b"changed before copy")
    with pytest.raises(AppError) as raised:
        env.initial._write_config(env.pc3, digest, PREFERRED, env.candidate)
    assert raised.value.code == "E210"
    root = env.root / "DWG-to-PDF/autocad-auto"
    assert not root.exists() or not list(root.iterdir())


def test_each_preparation_preserves_previous_generated_config(monkeypatch, tmp_path):
    env = setup_environment(monkeypatch, tmp_path)
    first = Path(env.initial.prepare_autocad_config(env.candidate))
    before = (first.read_bytes(), first.stat().st_mtime_ns)
    second = Path(env.initial.prepare_autocad_config(env.candidate))
    assert first.parent != second.parent
    assert (first.read_bytes(), first.stat().st_mtime_ns) == before


def test_ownership_failure_is_propagated(monkeypatch, tmp_path):
    env = setup_environment(monkeypatch, tmp_path)
    def fail_enter(self):
        raise AppError("E201", "ownership not proven")
    monkeypatch.setattr(env.session, "__enter__", fail_enter)
    with pytest.raises(AppError) as raised:
        env.initial.prepare_autocad_config(env.candidate)
    assert raised.value.code == "E201"
    assert "copy_open" not in env.events


def test_shutdown_timeout_rejects_config_and_closes_exact_handle(monkeypatch, tmp_path):
    env = setup_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(sys.modules["win32event"], "WaitForSingleObject", lambda handle, timeout: 258)
    with pytest.raises(AppError) as raised:
        env.initial.prepare_autocad_config(env.candidate)
    assert raised.value.code == "E201"
    assert env.events[-1] == ("handle_close", 43)
    assert not (env.root / "DWG-to-PDF/autocad-auto").exists()


def test_completion_handle_failure_closes_owned_session(monkeypatch, tmp_path):
    env = setup_environment(monkeypatch, tmp_path)
    def fail_capture(*args):
        raise RuntimeError("native handle unavailable")
    monkeypatch.setattr(sys.modules["win32api"], "DuplicateHandle", fail_capture)
    with pytest.raises(AppError) as raised:
        env.initial.prepare_autocad_config(env.candidate)
    assert raised.value.code == "E201"
    assert env.events == ["owned_session_open", "owned_session_close"]
    assert not (env.root / "DWG-to-PDF/autocad-auto").exists()
