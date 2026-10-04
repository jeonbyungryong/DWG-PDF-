from __future__ import annotations

from pathlib import Path
import gc
import hashlib
import os
from types import SimpleNamespace
import uuid

import pythoncom
import pytest

from dwg_to_pdf.domain import Point, Rect
from dwg_to_pdf.errors import AppError
from dwg_to_pdf.gstarcad.com_session import GstarSession
from dwg_to_pdf.gstarcad.com_session import _gstar_pids
from dwg_to_pdf.gstarcad.media_resolver import require_plot_environment
from dwg_to_pdf.gstarcad.plot_settings import apply_plot_settings
from dwg_to_pdf.gstarcad.plotter import plot_to_file
from dwg_to_pdf.gstarcad.template_detector import DetectionLimits, detect_scale_cell, verify_rotation
from dwg_to_pdf.pdf_validator import validate_pdf
from dwg_to_pdf.temp_workspace import SourceWorkspace, publish_pdf
from dwg_to_pdf.templates.profile_store import ProfileStore
from dwg_to_pdf.templates.structural_fallback import (
    choose_profile_by_structure,
    profiles_for_scale_cell,
)


class FakeLayout:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    def SetWindowToPlot(self, lower_left, upper_right) -> None:
        self.calls.append((lower_left, upper_right))


class FreshDrawingLayout(FakeLayout):
    def __init__(self) -> None:
        super().__init__()
        self.window_is_defined = False
        self.setting_order: list[str] = []

    def SetWindowToPlot(self, lower_left, upper_right) -> None:
        super().SetWindowToPlot(lower_left, upper_right)
        self.window_is_defined = True
        self.setting_order.append("SetWindowToPlot")

    @property
    def PlotType(self) -> int:
        return 4 if self.window_is_defined else 0

    @PlotType.setter
    def PlotType(self, value: int) -> None:
        if value == 4 and not self.window_is_defined:
            raise ValueError("Invalid input")
        self.setting_order.append("PlotType")


@pytest.mark.parametrize(
    ("frame_rotation", "expected_plot_rotation"),
    [(0, 0), (90, 3), (180, 2), (270, 1)],
)
def test_computed_window_and_exact_settings_are_applied_without_saved_window_getter(
    frame_rotation: int, expected_plot_rotation: int
) -> None:
    layout = FakeLayout()
    apply_plot_settings(
        layout,
        Rect(Point(100, 200), Point(520, 497)),
        frame_rotation,
        "ISO_A4",
    )
    assert len(layout.calls) == 1
    lower, upper = layout.calls[0]
    assert lower.varianttype == pythoncom.VT_ARRAY | pythoncom.VT_R8
    assert upper.varianttype == pythoncom.VT_ARRAY | pythoncom.VT_R8
    assert tuple(lower.value) == (100.0, 200.0)
    assert tuple(upper.value) == (520.0, 497.0)
    assert layout.ConfigName == "DWG To PDF.pc3"
    assert layout.CanonicalMediaName == "ISO_A4"
    assert layout.PlotType == 4
    assert layout.UseStandardScale is True
    assert layout.StandardScale == 0
    assert layout.CenterPlot is True
    assert layout.StyleSheet == "monochrome.ctb"
    assert layout.PlotWithLineweights is True
    assert layout.PlotWithPlotStyles is True
    assert layout.PlotRotation == expected_plot_rotation


def test_fresh_drawing_defines_window_before_selecting_window_plot_type() -> None:
    layout = FreshDrawingLayout()

    apply_plot_settings(
        layout,
        Rect(Point(0, 0), Point(420, 297)),
        0,
        "User77",
    )

    assert layout.setting_order[:2] == ["SetWindowToPlot", "PlotType"]


@pytest.mark.parametrize("rotation", [True, False, -90, 45, 360, 90.0])
def test_plot_settings_reject_invalid_rotation(rotation: object) -> None:
    with pytest.raises(AppError) as raised:
        apply_plot_settings(FakeLayout(), Rect(Point(0, 0), Point(1, 1)), rotation, "ISO_A4")
    assert raised.value.code == "E307"


def test_session_opens_only_active_workspace_copy_writable(tmp_path: Path) -> None:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"AC1032fixture")
    opened: list[tuple[str, bool]] = []
    raw = SimpleNamespace(ReadOnly=False, Close=lambda save: None)
    session = GstarSession("unused")
    session.app = SimpleNamespace(
        Documents=SimpleNamespace(Open=lambda path, readonly: opened.append((path, readonly)) or setattr(raw, "FullName", path) or raw)
    )
    session._owns_app = True

    workspace = SourceWorkspace(source)
    with pytest.raises(AppError):
        with session.working_document(workspace):
            pass
    with workspace:
        with session.working_document(workspace) as wrapped:
            assert wrapped.raw is raw
            assert opened == [(str(workspace.authorized_copy()), False)]
            with pytest.raises(AppError) as second:
                with session.working_document(workspace):
                    pass
            assert second.value.code == "E201"
        assert raw.Close is not None
    with pytest.raises(AppError):
        with session.working_document(workspace):
            pass


def test_working_document_closes_before_workspace_cleanup_on_body_failure(tmp_path: Path) -> None:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"AC1032fixture")
    close_arguments: list[bool] = []

    class LockedRaw:
        ReadOnly = False

        def __init__(self, path: str) -> None:
            self.FullName = path
            self.handle = Path(path).open("rb")

        def Close(self, save: bool) -> None:
            close_arguments.append(save)
            self.handle.close()

    session = GstarSession("unused")
    session.app = SimpleNamespace(
        Documents=SimpleNamespace(Open=lambda path, readonly: LockedRaw(path))
    )
    session._owns_app = True

    with pytest.raises(RuntimeError, match="detection failed"):
        with SourceWorkspace(source) as workspace:
            temp_dir = workspace.authorized_copy().parent
            with session.working_document(workspace):
                raise RuntimeError("detection failed")

    assert close_arguments == [False]
    assert not temp_dir.exists()


def test_session_rejects_fabricated_workspace_even_if_it_returns_an_existing_dwg(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"dwg")
    session = GstarSession("unused")
    session.app = SimpleNamespace(
        Documents=SimpleNamespace(
            Open=lambda path, readonly: pytest.fail("fabricated workspace must not reach COM")
        )
    )
    session._owns_app = True
    fake_workspace = SimpleNamespace(authorized_copy=lambda: source)

    with pytest.raises(AppError) as raised:
        with session.working_document(fake_workspace):
            pass
    assert raised.value.code == "E400"


@pytest.mark.parametrize("mode", ["false", "exception", "missing", "zero", "unstable"])
def test_plot_failure_preserves_existing_final_and_removes_partial_temp(
    tmp_path: Path, monkeypatch, mode: str
) -> None:
    temporary = tmp_path / "temporary.pdf"
    final = tmp_path / "final.pdf"
    final.write_bytes(b"old valid pdf")

    class Plot:
        def PlotToFile(self, output: str):
            if mode == "exception":
                Path(output).write_bytes(b"partial")
                raise PermissionError("COM failed")
            if mode == "missing":
                return True
            if mode == "zero":
                Path(output).write_bytes(b"")
                return True
            Path(output).write_bytes(b"partial" if mode == "false" else b"%PDF-" + b"x" * 200)
            return mode != "false"

    document = SimpleNamespace(
        Plot=Plot(),
        GetVariable=lambda name: 3,
        SetVariable=lambda name, value: None,
    )
    if mode == "unstable":
        changing = iter(
            SimpleNamespace(st_size=205, st_mtime_ns=index) for index in range(20)
        )
        monkeypatch.setattr(
            "dwg_to_pdf.gstarcad.plotter._stat_path", lambda path: next(changing)
        )
    checks = 2 if mode == "unstable" else 1
    with pytest.raises(AppError):
        plot_to_file(document, temporary, stability_checks=checks, stability_interval_sec=0)
    assert final.read_bytes() == b"old valid pdf"
    assert not temporary.exists()


def test_plot_cleanup_failure_preserves_existing_final(
    tmp_path: Path, monkeypatch
) -> None:
    temporary = tmp_path / "temporary.pdf"
    final = tmp_path / "final.pdf"
    final.write_bytes(b"old valid pdf")

    class Plot:
        def PlotToFile(self, output: str) -> bool:
            Path(output).write_bytes(b"partial")
            return False

    document = SimpleNamespace(
        Plot=Plot(),
        GetVariable=lambda name: 3,
        SetVariable=lambda name, value: None,
    )
    monkeypatch.setattr(
        "dwg_to_pdf.gstarcad.plotter._remove_file",
        lambda path: (_ for _ in ()).throw(PermissionError("locked")),
        raising=False,
    )

    with pytest.raises(AppError) as raised:
        plot_to_file(document, temporary, stability_checks=1, stability_interval_sec=0)
    assert raised.value.code == "E410"
    assert final.read_bytes() == b"old valid pdf"


def _identity(path: Path) -> tuple[str, int]:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper(), path.stat().st_mtime_ns


@pytest.mark.gstarcad
@pytest.mark.skipif("GSTARCAD_PLOT_DWGS" not in os.environ, reason="set GSTARCAD_PLOT_DWGS")
def test_real_com_plots_computed_windows_sequentially_to_validated_pdfs() -> None:
    sources = tuple(
        Path(value).resolve(strict=True)
        for value in os.environ["GSTARCAD_PLOT_DWGS"].split(";")
        if value.strip()
    )
    assert len(sources) >= 3
    profile_root = Path(os.environ["GSTARCAD_PROFILE_SOURCE_ROOT"]).resolve(strict=True)
    output_root = Path(os.environ["GSTARCAD_PLOT_OUTPUT_ROOT"]).resolve(strict=False)
    output_root.mkdir(parents=True, exist_ok=True)
    store = ProfileStore(Path("template_profiles"), source_root=profile_root)
    store.load_all()
    before = {source: _identity(source) for source in sources}
    user_pids = _gstar_pids()
    results = []

    with GstarSession(os.environ.get("GSTARCAD_PROG_ID", "GStarCAD.Application.26")) as session:
        owned_pid = session.owned_pid
        assert owned_pid is not None and owned_pid not in user_pids

        # Prove the failure boundary closes the writable copy before its
        # SourceWorkspace is removed, then reuse the same owned PID.
        with pytest.raises(RuntimeError, match="intentional lifecycle failure"):
            with SourceWorkspace(sources[0]) as failed_workspace:
                failed_temp_dir = failed_workspace.authorized_copy().parent
                with session.working_document(failed_workspace):
                    raise RuntimeError("intentional lifecycle failure")
        assert not failed_temp_dir.exists()
        assert session.owned_pid == owned_pid

        for source in sources:
            unique = uuid.uuid4().hex
            temporary_pdf = output_root / f".{source.stem}.{unique}.tmp.pdf"
            final_pdf = output_root / f"{source.stem}.{unique}.pdf"
            with SourceWorkspace(source) as workspace:
                with session.working_document(workspace) as document:
                    cell = detect_scale_cell(document, DetectionLimits(64, 5000), store.all())
                    profiles = profiles_for_scale_cell(cell, store)
                    decision = choose_profile_by_structure(
                        cell,
                        profiles,
                        lambda profile, candidate: verify_rotation(document, profile, candidate),
                        minimum_score=0.80,
                        minimum_gap=0.01,
                    )
                    layout = document.raw.ActiveLayout
                    media = require_plot_environment(layout, ("User77",))
                    apply_plot_settings(
                        layout,
                        decision.candidate.plot_window,
                        decision.candidate.rotation,
                        media,
                    )
                    plot_to_file(document.raw, temporary_pdf)
                    layout = None
                    gc.collect()
                validation = publish_pdf(temporary_pdf, final_pdf)
                results.append(
                    (
                        source,
                        final_pdf,
                        decision.candidate.profile_id,
                        decision.candidate.rotation,
                        decision.candidate.plot_window,
                        validation,
                    )
                )
                assert session.owned_pid == owned_pid

    assert {source: _identity(source) for source in sources} == before
    assert owned_pid not in _gstar_pids()
    assert user_pids <= _gstar_pids()
    for source, pdf, profile_id, rotation, window, validation in results:
        assert validate_pdf(pdf) == validation
        print(
            f"source={source}; output={pdf}; profile={profile_id}; rotation={rotation}; "
            f"window=({window.lower_left.x},{window.lower_left.y})-"
            f"({window.upper_right.x},{window.upper_right.y}); "
            f"page_mm=({validation.width_mm:.4f},{validation.height_mm:.4f}); "
            f"sha256={before[source][0]}; mtime_ns={before[source][1]}; "
            f"owned_pid={owned_pid}; preexisting_pids={sorted(user_pids)}"
        )
