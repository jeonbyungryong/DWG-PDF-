from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from dwg_to_pdf.gstarcad.com_session import GstarSession, _gstar_pids
from dwg_to_pdf.gstarcad.template_detector import DetectionLimits, detect_scale_candidates, detect_scale_cell, verify_rotation
from dwg_to_pdf.templates.plot_window_transform import compute_candidate
from dwg_to_pdf.templates.profile_store import ProfileStore
from dwg_to_pdf.templates.scale_label import parse_internal_scale
from dwg_to_pdf.templates.scale_label import parse_reference_filename


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


@pytest.mark.gstarcad
@pytest.mark.skipif("GSTARCAD_TEST_DWGS" not in os.environ, reason="set GSTARCAD_TEST_DWGS")
def test_one_owned_pid_opens_multiple_drawings_sequentially_without_source_changes() -> None:
    sources = tuple(
        Path(value).resolve(strict=True)
        for value in os.environ["GSTARCAD_TEST_DWGS"].split(";")
        if value.strip()
    )
    assert len(sources) >= 3
    before = {source: (_sha256(source), source.stat().st_mtime_ns) for source in sources}
    user_pids_before = _gstar_pids()
    assert user_pids_before, "start a user-owned GstarCAD process before running this test"

    with GstarSession(os.environ.get("GSTARCAD_PROG_ID", "GStarCAD.Application.26")) as session:
        owned_pid = session.owned_pid
        assert owned_pid is not None
        assert owned_pid not in user_pids_before
        assert user_pids_before <= _gstar_pids()
        print(f"owned_pid={owned_pid}; pre_existing_user_pids={sorted(user_pids_before)}")
        for source in sources:
            document = session.open_readonly_copy(source)
            assert document.raw.ReadOnly is True
            snapshots = document.filtered_snapshots(("TEXT", "MTEXT", "INSERT"))
            assert snapshots
            assert {str(item["type"]) for item in snapshots} <= {"TEXT", "MTEXT", "ATTRIB", "INSERT"}
            candidates = detect_scale_candidates(document, DetectionLimits(64, 5000))
            assert candidates
            session.close_document()
            assert session.owned_pid == owned_pid

    assert {
        source: (_sha256(source), source.stat().st_mtime_ns) for source in sources
    } == before
    pids_after = _gstar_pids()
    assert owned_pid not in pids_after
    assert user_pids_before <= pids_after
    for source, (sha256, mtime_ns) in before.items():
        print(f"preserved={source}; sha256={sha256}; mtime_ns={mtime_ns}")


@pytest.mark.gstarcad
@pytest.mark.skipif(
    "GSTARCAD_WINDOW_LEARNING_DWGS" not in os.environ,
    reason="set GSTARCAD_WINDOW_LEARNING_DWGS",
)
def test_window_learning_targets_never_influence_computed_profile_window() -> None:
    sources = tuple(
        Path(value).resolve(strict=True)
        for value in os.environ["GSTARCAD_WINDOW_LEARNING_DWGS"].split(";")
        if value.strip()
    )
    assert len(sources) == 2
    source_root = sources[0].parent.parent
    store = ProfileStore(Path("template_profiles"), source_root=source_root)
    store.load_all()
    before = {source: (_sha256(source), source.stat().st_mtime_ns) for source in sources}
    user_pids_before = _gstar_pids()
    assert user_pids_before, "start a user-owned GstarCAD process before running this test"

    with GstarSession(os.environ.get("GSTARCAD_PROG_ID", "GStarCAD.Application.26")) as session:
        owned_pid = session.owned_pid
        assert owned_pid not in user_pids_before
        for source in sources:
            document = session.open_readonly_copy(source)
            candidate = detect_scale_candidates(document, DetectionLimits(64, 5000))[0]
            profile = store.find(parse_internal_scale(candidate.token))
            computed = compute_candidate(profile, candidate, 0).plot_window
            saved_lower, saved_upper = document.raw.ActiveLayout.GetWindowToPlot()
            saved_dimensions = (
                float(saved_upper[0]) - float(saved_lower[0]),
                float(saved_upper[1]) - float(saved_lower[1]),
            )
            assert (computed.width, computed.height) != pytest.approx(saved_dimensions)
            assert (computed.width, computed.height) == pytest.approx(
                tuple(float(value) for value in profile.scale.a3_model_size())
            )
            print(
                f"window_independent={source}; computed={(computed.width, computed.height)}; "
                f"diagnostic_saved={saved_dimensions}; owned_pid={owned_pid}"
            )
            session.close_document()

    assert {source: (_sha256(source), source.stat().st_mtime_ns) for source in sources} == before
    assert owned_pid not in _gstar_pids()
    assert user_pids_before <= _gstar_pids()


@pytest.mark.gstarcad
@pytest.mark.skipif("GSTARCAD_VERIFY_DWGS" not in os.environ, reason="set GSTARCAD_VERIFY_DWGS")
def test_registered_reference_signatures_score_exactly_in_bounded_real_com_queries() -> None:
    sources = tuple(Path(value).resolve(strict=True) for value in os.environ["GSTARCAD_VERIFY_DWGS"].split(";") if value.strip())
    assert len(sources) >= 3
    store = ProfileStore(Path("template_profiles"), source_root=sources[0].parent)
    store.load_all()
    before = {source: (_sha256(source), source.stat().st_mtime_ns) for source in sources}
    with GstarSession(os.environ.get("GSTARCAD_PROG_ID", "GStarCAD.Application.26")) as session:
        owned_pid = session.owned_pid
        for source in sources:
            document = session.open_readonly_copy(source)
            scale_candidate = detect_scale_candidates(document, DetectionLimits(64, 5000))[0]
            profile = store.find(parse_internal_scale(scale_candidate.token))
            frame_candidate = compute_candidate(profile, scale_candidate, 0)
            assert verify_rotation(document, profile, frame_candidate) == 1.0
            session.close_document()
    assert {source: (_sha256(source), source.stat().st_mtime_ns) for source in sources} == before
    assert owned_pid not in _gstar_pids()


@pytest.mark.gstarcad
@pytest.mark.skipif("GSTARCAD_CELL_DWGS" not in os.environ, reason="set GSTARCAD_CELL_DWGS")
def test_registered_measured_cells_detect_each_real_internal_scale() -> None:
    sources = tuple(
        Path(value).resolve(strict=True)
        for value in os.environ["GSTARCAD_CELL_DWGS"].split(";")
        if value.strip()
    )
    assert len(sources) >= 2
    store = ProfileStore(Path("template_profiles"), source_root=sources[0].parent)
    store.load_all()
    before = {source: (_sha256(source), source.stat().st_mtime_ns) for source in sources}
    with GstarSession(os.environ.get("GSTARCAD_PROG_ID", "GStarCAD.Application.26")) as session:
        owned_pid = session.owned_pid
        for source in sources:
            document = session.open_readonly_copy(source)
            cell = detect_scale_cell(document, DetectionLimits(64, 5000), store.all())
            assert cell.state == "valid"
            assert parse_internal_scale(cell.token or "") == parse_reference_filename(source)
            session.close_document()
    assert {source: (_sha256(source), source.stat().st_mtime_ns) for source in sources} == before
    assert owned_pid not in _gstar_pids()
