"""Live tests, deliberately NOT_RUN without the explicit AutoCAD environment."""
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from dwg_to_pdf.cad.factory import create_session, resolve_selection
from dwg_to_pdf.cad.discovery import discover_candidates
from dwg_to_pdf.cad.selection import select_candidate
from dwg_to_pdf.cad.process_ownership import provider_pids
from dwg_to_pdf.cad.validation import live_autocad_environment, require_process_cleanup
from dwg_to_pdf.configuration import load_config
from dwg_to_pdf.conversion_service import ConversionService
from dwg_to_pdf.orchestrator import run_jobs
from dwg_to_pdf.pdf_validator import validate_pdf
from dwg_to_pdf.temp_workspace import sha256
from dwg_to_pdf.templates.profile_store import ProfileStore, require_canonical_profiles

pytestmark = pytest.mark.autocad
ROOT = Path(__file__).parents[2]


def setup():
    config_path, sources = live_autocad_environment(os.environ)
    config = load_config(config_path)
    assert config.cad_provider == "autocad" and config.allow_experimental_autocad
    candidate = select_candidate(resolve_selection(config, None, None, False), discover_candidates("autocad"))
    profiles = ProfileStore(ROOT / "template_profiles", source_root=ROOT / "template_profiles")
    profiles.load_all()
    require_canonical_profiles(profiles.all())
    sources = tuple(path.resolve(strict=True) for path in sources)
    return config, candidate, profiles, sources


def evidence(sources):
    return {source: (sha256(source), source.stat().st_mtime_ns) for source in sources}


def convert_sources(config, candidate, profiles, sources, output):
    output.mkdir()
    before = evidence(sources)
    user_pids = provider_pids("autocad")
    assert user_pids, "G4 requires a user-opened AutoCAD process for coexistence validation"
    owned_pid = None
    outcomes = []
    try:
        with create_session(candidate) as session:
            owned_pid = session.owned_pid
            assert owned_pid is not None and owned_pid not in user_pids
            assert session.reported_version, "record actual COM Version before accepting evidence"
            service = ConversionService(config, profiles)
            for source in sources:
                result = service.convert_in_session(session, source, output, "overwrite")
                assert len(result.frames) == 1
                validate_pdf(result.frames[0].output, allow_duplicate_page_mode=True)
                outcomes.append(result)
    finally:
        after_pids = provider_pids("autocad")
        assert user_pids <= after_pids
        assert owned_pid is None or owned_pid not in after_pids
        assert evidence(sources) == before
    return outcomes


def test_autocad_preserves_source_and_user_process(tmp_path):
    config, candidate, profiles, sources = setup()
    convert_sources(config, candidate, profiles, sources[:1], tmp_path / "single")


def test_autocad_13_profiles_and_30_variants(tmp_path):
    config, candidate, profiles, sources = setup()
    assert len(sources) >= 43, "supply approved 13 templates plus at least 30 variants"
    approved = {json.loads(path.read_text(encoding="utf-8"))["source"]["sha256"].casefold()
                for path in (ROOT / "template_profiles").glob("*.json")}
    assert len(approved) == 13 and approved <= {sha256(path).casefold() for path in sources}
    off = convert_sources(replace(config, use_native_extraction=False), candidate, profiles, sources, tmp_path / "off")
    on = convert_sources(replace(config, use_native_extraction=True), candidate, profiles, sources, tmp_path / "on")
    decisions = lambda results: [(item.frames[0].scale, item.frames[0].rotation, item.frames[0].plot_window) for item in results]
    assert decisions(off) == decisions(on)
    def record(results):
        return [{"source": str(item.source), "sha256": sha256(item.source),
                 "numerator": str(item.frames[0].scale.numerator),
                 "denominator": str(item.frames[0].scale.denominator),
                 "rotation": item.frames[0].rotation,
                 "window": [item.frames[0].plot_window.lower_left.x, item.frames[0].plot_window.lower_left.y,
                            item.frames[0].plot_window.upper_right.x, item.frames[0].plot_window.upper_right.y],
                 "output": str(item.frames[0].output)} for item in results]
    (tmp_path / "matrix-decisions.json").write_text(json.dumps({"off": record(off), "on": record(on)}, indent=2), encoding="utf-8")


def test_autocad_failed_file_does_not_stop_next(tmp_path):
    config, candidate, profiles, sources = setup()
    broken = tmp_path / "invalid.dwg"
    broken.write_bytes(b"synthetic invalid DWG")
    output = tmp_path / "pdf"
    output.mkdir()
    before = evidence(sources[:1])
    user_pids = provider_pids("autocad")
    assert user_pids, "G4 requires a user-opened AutoCAD process"
    sessions = []
    acquired_pids = set()
    class RecordingSession:
        def __init__(self):
            self.session = create_session(candidate)
        def __getattr__(self, name):
            return getattr(self.session, name)
        def __enter__(self):
            self.session.__enter__()
            assert self.session.owned_pid is not None
            acquired_pids.add(self.session.owned_pid)
            return self
        def __exit__(self, *args):
            return self.session.__exit__(*args)
    def factory():
        session = RecordingSession()
        sessions.append(session)
        return session
    try:
        results = run_jobs(ConversionService(config, profiles), (broken, sources[0]), output, "overwrite", factory)
        assert [result.status for result in results] == ["failed", "success"]
        validate_pdf(results[1].outputs[0], allow_duplicate_page_mode=True)
    finally:
        assert evidence(sources[:1]) == before
        require_process_cleanup(user_pids, acquired_pids, provider_pids("autocad"))
        assert all(session.owned_pid is None for session in sessions)
