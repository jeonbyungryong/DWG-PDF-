"""Portable GstarCAD regression; no CAD execution without explicit opt-in."""
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from dwg_to_pdf.cad.factory import create_session, resolve_selection
from dwg_to_pdf.cad.discovery import discover_candidates
from dwg_to_pdf.cad.selection import select_candidate
from dwg_to_pdf.cad.process_ownership import provider_pids
from dwg_to_pdf.cad.validation import require_process_cleanup
from dwg_to_pdf.configuration import load_config
from dwg_to_pdf.conversion_service import ConversionService
from dwg_to_pdf.orchestrator import run_jobs
from dwg_to_pdf.pdf_validator import validate_pdf
from dwg_to_pdf.temp_workspace import sha256
from dwg_to_pdf.templates.profile_store import ProfileStore, require_canonical_profiles
from dwg_to_pdf import __version__
from dwg_to_pdf.cad.diagnostics import diagnostic_scope
from dwg_to_pdf.gstarcad.document import GstarDocument
from dwg_to_pdf.gstarcad.bulk_snapshot import NativeExtractionUnavailable

pytestmark = pytest.mark.gstarcad
ROOT = Path(os.environ.get("GSTAR_REGRESSION_REPO", ".")).resolve()


def observe_extraction(original, events):
    def observed(*args, **kwargs):
        try:
            result = original(*args, **kwargs)
        except NativeExtractionUnavailable:
            events.append("native_unavailable_COM_fallback")
            print("EXTRACTION_EVIDENCE native_unavailable_COM_fallback", flush=True)
            raise
        events.append("native_success")
        print("EXTRACTION_EVIDENCE native_success", flush=True)
        return result
    return observed


@pytest.fixture(autouse=True)
def recorded_diagnostics(monkeypatch, tmp_path):
    if os.environ.get("GSTAR_REGRESSION_ENABLED") != "1":
        yield
        return
    _, candidate, _, _ = setup()
    events = []
    monkeypatch.setattr(GstarDocument, "_extract_snapshot", observe_extraction(GstarDocument._extract_snapshot, events))
    try:
        with diagnostic_scope(candidate, __version__):
            yield
    finally:
        (tmp_path / "extraction-evidence.json").write_text(json.dumps({"provider": candidate.provider, "prog_id": candidate.prog_id, "events": events}, indent=2), encoding="utf-8")


def setup():
    if os.environ.get("GSTAR_REGRESSION_ENABLED") != "1":
        pytest.skip("GstarCAD NOT_RUN: explicit GSTAR_REGRESSION_ENABLED=1 required")
    kit = Path(__file__).resolve().parent
    cases = json.loads((kit / "inputs-manifest.json").read_text(encoding="utf-8"))["cases"]
    sources = tuple(kit / "inputs" / case["file"] for case in cases)
    assert len(cases) == 43
    assert all(sha256(path).upper() == case["sha256"].upper() for path, case in zip(sources, cases))
    config = load_config(Path(os.environ.get("GSTAR_REGRESSION_CONFIG", str(kit / "gstarcad-approved.toml"))))
    assert config.cad_provider == "gstarcad" and config.autocad_pc3_path is None
    candidate = select_candidate(resolve_selection(config, None, None, False), discover_candidates("gstarcad"))
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
    user_pids = provider_pids("gstarcad")
    assert user_pids, "G3 requires a user-opened GstarCAD process for coexistence validation"
    owned_pid = None
    outcomes = []
    metadata = {"provider": candidate.provider, "prog_id": candidate.prog_id,
                "native_setting": config.use_native_extraction, "source_count": len(sources)}
    try:
        with create_session(candidate) as session:
            owned_pid = session.owned_pid
            assert owned_pid is not None and owned_pid not in user_pids
            assert session.reported_version, "record actual COM Version before accepting evidence"
            metadata.update(reported_version=session.reported_version, owned_pid=owned_pid)
            service = ConversionService(config, profiles)
            for source in sources:
                result = service.convert_in_session(session, source, output, "overwrite")
                assert len(result.frames) == 1
                validate_pdf(result.frames[0].output, allow_duplicate_page_mode=False)
                outcomes.append(result)
    finally:
        after_pids = provider_pids("gstarcad")
        metadata.update(user_pids_before=sorted(user_pids), user_pids_after=sorted(after_pids),
                        sources_unchanged=evidence(sources) == before,
                        owned_pid_closed=owned_pid is None or owned_pid not in after_pids)
        (output.parent / f"{output.name}-session.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        assert user_pids <= after_pids
        assert owned_pid is None or owned_pid not in after_pids
        assert evidence(sources) == before
    return outcomes


def test_gstarcad_preserves_source_and_user_process(tmp_path):
    config, candidate, profiles, sources = setup()
    convert_sources(config, candidate, profiles, sources[:1], tmp_path / "single")


def test_gstarcad_13_profiles_and_30_variants(tmp_path):
    config, candidate, profiles, sources = setup()
    assert len(sources) >= 43, "supply approved 13 templates plus at least 30 variants"
    approved = {json.loads(path.read_text(encoding="utf-8"))["source"]["sha256"].casefold()
                for path in (ROOT / "template_profiles").glob("*.json")}
    assert len(approved) == 13 and approved <= {sha256(path).casefold() for path in sources}
    off = convert_sources(replace(config, use_native_extraction=False), candidate, profiles, sources, tmp_path / "off")
    on = convert_sources(replace(config, use_native_extraction=True), candidate, profiles, sources, tmp_path / "on")
    decisions = lambda results: [(item.frames[0].scale, item.frames[0].rotation, item.frames[0].plot_window) for item in results]
    assert decisions(off) == decisions(on)
    manifest = json.loads((Path(__file__).resolve().parent / "inputs-manifest.json").read_text(encoding="utf-8"))
    for results in (off, on):
        for result, case in zip(results, manifest["cases"]):
            frame = result.frames[0]
            assert str(frame.scale.numerator) == case["scale"]["numerator"]
            assert str(frame.scale.denominator) == case["scale"]["denominator"]
            assert frame.rotation == case["rotation"]
            actual_window = [frame.plot_window.lower_left.x, frame.plot_window.lower_left.y,
                             frame.plot_window.upper_right.x, frame.plot_window.upper_right.y]
            assert max(abs(a-b) for a,b in zip(actual_window,case["window"])) < 0.001

    def record(results):
        return [{"source": str(item.source), "sha256": sha256(item.source),
                 "numerator": str(item.frames[0].scale.numerator),
                 "denominator": str(item.frames[0].scale.denominator),
                 "rotation": item.frames[0].rotation,
                 "window": [item.frames[0].plot_window.lower_left.x, item.frames[0].plot_window.lower_left.y,
                            item.frames[0].plot_window.upper_right.x, item.frames[0].plot_window.upper_right.y],
                 "output": str(item.frames[0].output)} for item in results]
    (tmp_path / "matrix-decisions.json").write_text(json.dumps({"off": record(off), "on": record(on)}, indent=2), encoding="utf-8")


def test_gstarcad_failed_file_does_not_stop_next(tmp_path):
    config, candidate, profiles, sources = setup()
    broken = tmp_path / "invalid.dwg"
    broken.write_bytes(b"synthetic invalid DWG")
    output = tmp_path / "pdf"
    output.mkdir()
    before = evidence(sources[:1])
    user_pids = provider_pids("gstarcad")
    assert user_pids, "G3 requires a user-opened GstarCAD process"
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
        validate_pdf(results[1].outputs[0], allow_duplicate_page_mode=False)
    finally:
        assert evidence(sources[:1]) == before
        require_process_cleanup(user_pids, acquired_pids, provider_pids("gstarcad"))
        assert all(session.owned_pid is None for session in sessions)
