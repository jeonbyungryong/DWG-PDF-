from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from dwg_to_pdf.configuration import AppConfig
from dwg_to_pdf.conversion_service import ConversionService
from dwg_to_pdf.domain import FrameCandidate, MatchDecision, Point, Rect, ScaleRatio
from dwg_to_pdf.errors import AppError
from dwg_to_pdf.gstarcad.document import GstarDocument
from dwg_to_pdf import temp_workspace as workspace_module
from dwg_to_pdf.temp_workspace import publish_pdf as actual_publish_pdf


class FakeSession:
    def __init__(self, document: object) -> None:
        self.document = document
        self.workspaces: list[object] = []

    @contextmanager
    def working_document(self, workspace: object):
        self.workspaces.append(workspace)
        yield self.document


class SavedWindowGetterSentinel:
    def __init__(self) -> None:
        self.windows: list[tuple[object, object]] = []

    def GetWindowToPlot(self) -> object:
        raise AssertionError("conversion must not read the saved Plot Window")

    def SetWindowToPlot(self, lower_left: object, upper_right: object) -> None:
        self.windows.append((lower_left, upper_right))


def _write_pdf(path: Path, pages: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if pages != 1:
        path.write_bytes(b"old final bytes")
        return
    image = Image.new("RGB", (842, 595), "white")
    try:
        ImageDraw.Draw(image).line((20, 20, 822, 575), fill="black", width=3)
        image.save(path, "PDF", resolution=72.0)
    finally:
        image.close()


def _config() -> AppConfig:
    return AppConfig(
        prog_id="GStarCAD.Application.26",
        auto_match_enabled=True,
        plotter_name="DWG To PDF.pc3",
        media_width_mm=297.0,
        media_height_mm=210.0,
        style_sheet="monochrome.ctb",
        preferred_media_names=("User77",),
        matching_threshold=0.8,
        minimum_score_gap=0.1,
    )


def test_convert_in_session_uses_the_supplied_session_and_computed_plot_window(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"drawing")
    output_dir = tmp_path / "output"
    window = Rect(Point(1, 2), Point(3, 4))
    candidate = FrameCandidate("p", SimpleNamespace(), 0, window, window, 0.0)
    decision = MatchDecision(candidate, 0.9, 0.2)
    raw = SimpleNamespace(ActiveLayout=object())
    document = GstarDocument(raw)
    session = FakeSession(document)
    profile = SimpleNamespace(profile_id="p", scale=ScaleRatio(1, 1))
    service = ConversionService(_config(), SimpleNamespace(all=lambda: (profile,)))
    calls: dict[str, object] = {}

    monkeypatch.setattr("dwg_to_pdf.conversion_service.require_stable", lambda path: None)
    monkeypatch.setattr("dwg_to_pdf.conversion_service.detect_scale_cell", lambda *args: object())
    monkeypatch.setattr("dwg_to_pdf.conversion_service.profiles_for_scale_cell", lambda *args: (profile,))
    monkeypatch.setattr("dwg_to_pdf.conversion_service.choose_profile_by_structure", lambda *args: decision)
    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.require_plot_environment", lambda *args: "User77")
    monkeypatch.setattr(
        "dwg_to_pdf.gstarcad.document.apply_plot_settings",
        lambda layout, received_window, rotation, media: calls.update(
            layout=layout, window=received_window, rotation=rotation, media=media
        ),
    )
    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.plot_to_file", lambda raw, path: None)
    monkeypatch.setattr("dwg_to_pdf.conversion_service.publish_pdf", lambda temporary, final: None)

    outcome = service.convert_in_session(session, source, output_dir, "overwrite")

    assert len(session.workspaces) == 1
    assert calls == {"layout": raw.ActiveLayout, "window": window, "rotation": 0, "media": "User77"}
    assert outcome.source == source.resolve()
    assert outcome.frames[0].output == output_dir / "source.pdf"


def test_convert_in_session_orders_plot_then_workspace_identity_then_publish_without_saved_window_getter(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"drawing")
    output_dir = tmp_path / "output"
    window = Rect(Point(1, 2), Point(3, 4))
    candidate = FrameCandidate("p", SimpleNamespace(), 0, window, window, 0.0)
    decision = MatchDecision(candidate, 0.9, 0.2)
    layout = SavedWindowGetterSentinel()
    raw = SimpleNamespace(ActiveLayout=layout)
    profile = SimpleNamespace(profile_id="p", scale=ScaleRatio(1, 1))
    service = ConversionService(_config(), SimpleNamespace(all=lambda: (profile,)))
    session = FakeSession(GstarDocument(raw))
    events: list[str] = []
    real_verify_identity = workspace_module._verify_source_identity

    monkeypatch.setattr("dwg_to_pdf.conversion_service.require_stable", lambda path: None)
    monkeypatch.setattr("dwg_to_pdf.conversion_service.detect_scale_cell", lambda *args: object())
    monkeypatch.setattr("dwg_to_pdf.conversion_service.profiles_for_scale_cell", lambda *args: (profile,))
    monkeypatch.setattr("dwg_to_pdf.conversion_service.choose_profile_by_structure", lambda *args: decision)
    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.require_plot_environment", lambda *args: "User77")
    monkeypatch.setattr(
        "dwg_to_pdf.gstarcad.document.plot_to_file",
        lambda raw_document, temporary: events.append("plot") or _write_pdf(temporary),
    )

    def observed_identity(*args: object):
        events.append("identity")
        return real_verify_identity(*args)

    def observed_publish(temporary: Path, final: Path):
        events.append("publish")
        return actual_publish_pdf(temporary, final)

    monkeypatch.setattr(workspace_module, "_verify_source_identity", observed_identity)
    monkeypatch.setattr("dwg_to_pdf.conversion_service.publish_pdf", observed_publish)

    outcome = service.convert_in_session(session, source, output_dir, "overwrite")

    assert events == ["plot", "identity", "publish"]
    assert len(session.workspaces) == 1
    assert len(layout.windows) == 1
    assert outcome.frames[0].output.read_bytes()


def test_convert_in_session_preserves_old_final_when_workspace_identity_gate_fails_after_plot(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"drawing")
    output_dir = tmp_path / "output"
    final = output_dir / "source.pdf"
    _write_pdf(final, pages=2)
    old_final = final.read_bytes()
    window = Rect(Point(1, 2), Point(3, 4))
    candidate = FrameCandidate("p", SimpleNamespace(), 0, window, window, 0.0)
    decision = MatchDecision(candidate, 0.9, 0.2)
    profile = SimpleNamespace(profile_id="p", scale=ScaleRatio(1, 1))
    service = ConversionService(_config(), SimpleNamespace(all=lambda: (profile,)))
    session = FakeSession(GstarDocument(SimpleNamespace(ActiveLayout=SavedWindowGetterSentinel())))

    monkeypatch.setattr("dwg_to_pdf.conversion_service.require_stable", lambda path: None)
    monkeypatch.setattr("dwg_to_pdf.conversion_service.detect_scale_cell", lambda *args: object())
    monkeypatch.setattr("dwg_to_pdf.conversion_service.profiles_for_scale_cell", lambda *args: (profile,))
    monkeypatch.setattr("dwg_to_pdf.conversion_service.choose_profile_by_structure", lambda *args: decision)
    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.require_plot_environment", lambda *args: "User77")

    def successful_plot_then_source_change(raw_document: object, temporary: Path) -> None:
        _write_pdf(temporary)
        source.write_bytes(b"source changed after plotting")

    monkeypatch.setattr("dwg_to_pdf.gstarcad.document.plot_to_file", successful_plot_then_source_change)

    with pytest.raises(AppError) as raised:
        service.convert_in_session(session, source, output_dir, "overwrite")

    assert raised.value.code == "E400"
    assert final.read_bytes() == old_final
    assert not tuple(output_dir.glob(".*.tmp.pdf"))


def test_convert_in_session_wraps_source_disappearance_after_stability_check(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.dwg"
    source.write_bytes(b"drawing")
    service = ConversionService(_config(), SimpleNamespace(all=lambda: ()))

    def stable_then_disappear(path: Path) -> None:
        source.unlink()

    monkeypatch.setattr("dwg_to_pdf.conversion_service.require_stable", stable_then_disappear)
    with pytest.raises(AppError) as raised:
        service.convert_in_session(FakeSession(object()), source, tmp_path / "output", "overwrite")

    assert raised.value.code == "E100"
    assert raised.value.path == source
