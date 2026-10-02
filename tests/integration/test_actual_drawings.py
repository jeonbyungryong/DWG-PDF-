"""Opt-in release harness for the six approved actual-drawing cases.

This test deliberately performs no COM work unless the release gate is fully
configured.  The current DispatchEx-return blocker is therefore not probed by
ordinary test runs.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import pytest

from dwg_to_pdf.configuration import load_config
from dwg_to_pdf.conversion_service import ConversionService
from dwg_to_pdf.domain import ConversionOutcome
from dwg_to_pdf.gstarcad.com_session import GstarSession, _gstar_pids
from dwg_to_pdf.release_harness import run_release_cases
from dwg_to_pdf.release_manifest import load_actual_cases
from dwg_to_pdf.pdf_validator import validate_pdf
from dwg_to_pdf.temp_workspace import sha256
from dwg_to_pdf.templates.profile_store import ProfileStore, require_canonical_profiles
from dwg_to_pdf.templates.scale_universe import scale_key


def _required_environment() -> dict[str, Path]:
    names = (
        "GSTARCAD_ACTUAL_CASES_JSON",
        "GSTARCAD_APPROVED_CONFIG",
        "GSTARCAD_TEMPLATE_SOURCE_ROOT",
    )
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        pytest.skip("release harness environment is not configured: " + ", ".join(missing))
    return {name: Path(os.environ[name]) for name in names}


class _RecordingService:
    """Preserve outcomes while delegating the full production conversion path."""

    def __init__(self, service: ConversionService) -> None:
        self._service = service
        self.outcomes: dict[Path, ConversionOutcome] = {}
        self.session_pids: list[int] = []

    def convert_in_session(self, session: GstarSession, source: Path, output_dir: Path, policy: str):
        assert session.owned_pid is not None
        self.session_pids.append(session.owned_pid)
        outcome = self._service.convert_in_session(session, source, output_dir, policy)
        self.outcomes[Path(source)] = outcome
        return outcome


def _profile_directory() -> Path:
    configured = os.environ.get("GSTARCAD_PROFILE_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "template_profiles"


def _source_evidence(sources: tuple[Path, ...]) -> dict[Path, tuple[str, int]]:
    return {source: (sha256(source), source.stat().st_mtime_ns) for source in sources}


@pytest.mark.gstarcad
def test_actual_drawing_release_harness_is_opt_in_and_calibrated(tmp_path: Path) -> None:
    paths = _required_environment()
    config = load_config(paths["GSTARCAD_APPROVED_CONFIG"])
    if not config.auto_match_enabled or config.matching_threshold is None or config.minimum_score_gap is None:
        pytest.fail("release gate failed: approved configuration must enable numeric auto-match threshold and gap")
    cases = load_actual_cases(paths["GSTARCAD_ACTUAL_CASES_JSON"])
    assert paths["GSTARCAD_TEMPLATE_SOURCE_ROOT"].is_dir(), "release gate failed: template source root is missing"
    profile_dir = _profile_directory()
    assert profile_dir.is_dir(), "release gate failed: profile directory is missing"
    store = ProfileStore(profile_dir, source_root=paths["GSTARCAD_TEMPLATE_SOURCE_ROOT"])
    store.load_all()
    require_canonical_profiles(store.all())

    sources = tuple(case.source for case in cases)
    evidence_before = _source_evidence(sources)
    user_pids_before = _gstar_pids()
    assert user_pids_before, "release gate failed: start a user-owned GstarCAD process before running"
    created_sessions: list[GstarSession] = []

    def factory() -> GstarSession:
        session = GstarSession(config.prog_id)
        created_sessions.append(session)
        return session

    recording = _RecordingService(ConversionService(config, store))
    try:
        results = run_release_cases(cases, tmp_path / "actual-release", recording, "overwrite", factory)
        assert [result.status for result in results] == ["success"] * len(cases)
        assert [result.source for result in results] == list(sources)
        assert len(created_sessions) == 1, "normal release must use one owned session"
        assert len(recording.session_pids) == len(cases)
        assert len(set(recording.session_pids)) == 1, "all release cases must share one owned PID"
        owned_pid = recording.session_pids[0]
        assert created_sessions[0].owned_pid is None, "batch terminal cleanup must clear owned PID"
        assert list(recording.outcomes) == list(sources)
        for case in cases:
            outcome = recording.outcomes[case.source]
            assert outcome.used_target_saved_window is False
            assert len(outcome.frames) == 1
            frame = outcome.frames[0]
            assert scale_key(frame.scale.numerator, frame.scale.denominator) == case.expected_scale
            assert frame.plot_window.lower_left.x < frame.plot_window.upper_right.x
            assert frame.plot_window.lower_left.y < frame.plot_window.upper_right.y
            assert all(
                math.isfinite(value)
                for value in (
                    frame.plot_window.lower_left.x,
                    frame.plot_window.lower_left.y,
                    frame.plot_window.upper_right.x,
                    frame.plot_window.upper_right.y,
                )
            )
            validation = validate_pdf(frame.output)
            assert validation.page_count == 1
            assert validation.nonblank is True
    finally:
        assert _source_evidence(sources) == evidence_before
        if recording.session_pids:
            assert recording.session_pids[0] not in _gstar_pids(), "owned GstarCAD PID must exit"
        assert user_pids_before <= _gstar_pids(), "release harness must not terminate user-owned GstarCAD"
